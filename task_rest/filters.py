"""Translate HTTP query parameters into TaskWarrior filter terms.

Only the attributes and modifiers listed in ATTRIBUTES are accepted. Anything else
raises FilterError, which the API turns into HTTP 400 before `task` is ever run.

Terms are plain strings that tasklib passes to `task` as separate argv items, so they
are never interpreted by a shell. Values are restricted (see _UNSAFE_RE and the
validators below) so a value cannot close its quotes or add extra filter terms.

Semantics follow TaskWarrior:
  ?start=           -> start:      attribute is NOT set
  ?start.any=       -> start.any:  attribute IS set
  ?start.none=      -> start.none: same as ?start=
  ?due.before=X     -> due.before:"X"
  ?tags=work        -> +work       (tags.not=work -> -work)
  ?tags.any=        -> tags.any:   (has at least one tag)
Repeated parameters are ANDed, as in TaskWarrior.
"""
import re
from datetime import datetime


class FilterError(ValueError):
    """Raised for an unsupported or malformed filter parameter (HTTP 400)."""


DATE_KEYWORDS = ('now', 'today', 'sod', 'eod', 'yesterday', 'tomorrow',
                 'sow', 'eow', 'som', 'eom', 'soy', 'eoy')

# Attribute -> (kind, allowed modifiers). Kind is 'str' or 'date'.
# Modifiers 'any' and 'none' take an empty value; the others take a value.
_STR_MODS = ('any', 'none', 'not', 'has')
_DATE_MODS = ('any', 'none', 'not', 'before', 'after')
ATTRIBUTES = {
    'status': ('str', ('not',)),
    'project': ('str', _STR_MODS),
    'priority': ('str', ('any', 'none', 'not')),
    'description': ('str', ('not', 'has')),
    'start': ('date', _DATE_MODS),
    'due': ('date', _DATE_MODS),
    'scheduled': ('date', _DATE_MODS),
    'wait': ('date', _DATE_MODS),
    'entry': ('date', _DATE_MODS),
    'end': ('date', _DATE_MODS),
}
SPECIAL = ('tags', 'uuid')
EMPTY_OK_MODS = ('any', 'none')
MAX_VALUE_LEN = 256

_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?Z?)?$')
_DATE_FORMATS = ('%Y-%m-%d', '%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S')
_UUID_RE = re.compile(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
_TAG_RE = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9_.-]*$')
# Control characters, double quote and backslash could break out of the quoting.
_UNSAFE_RE = re.compile(r'[\x00-\x1f\x7f"\\]')


def supported_names():
    names = []
    for attr, (_, mods) in sorted(ATTRIBUTES.items()):
        names.append(attr)
        names.extend('{}.{}'.format(attr, m) for m in mods)
    names.extend(['tags', 'tags.any', 'tags.none', 'tags.not', 'uuid'])
    return names


def _unknown(key):
    return FilterError('Unknown filter "{}". Supported: {}.'.format(
        key, ', '.join(supported_names())))


def _check_value(key, value):
    if len(value) > MAX_VALUE_LEN:
        raise FilterError('Value for "{}" is longer than {} characters.'.format(key, MAX_VALUE_LEN))
    if _UNSAFE_RE.search(value):
        raise FilterError('Value for "{}" contains unsupported characters '
                          '(quotes, backslash or control characters).'.format(key))


def _check_date(key, value):
    if value in DATE_KEYWORDS:
        return
    core = value[:-1] if value.endswith('Z') else value
    if _DATE_RE.match(value) and any(_parses(core, f) for f in _DATE_FORMATS):
        return
    raise FilterError('Invalid date for "{}": use YYYY-MM-DD, YYYY-MM-DDTHH:MM, '
                      'or one of {}.'.format(key, ', '.join(DATE_KEYWORDS)))


def _parses(text, fmt):
    try:
        datetime.strptime(text, fmt)
        return True
    except ValueError:
        return False


def _tags_term(key, mod, value):
    if mod in EMPTY_OK_MODS:
        if value:
            raise FilterError('"{}" takes no value; use an empty value.'.format(key))
        return 'tags.{}:'.format(mod)
    if not value:
        raise FilterError('"{}" needs a tag name, or use tags.any= / tags.none=.'.format(key))
    if not _TAG_RE.match(value):
        raise FilterError('Invalid tag name for "{}".'.format(key))
    return ('-' if mod == 'not' else '+') + value


def _uuid_term(key, value):
    if not _UUID_RE.match(value):
        raise FilterError('Invalid uuid for "{}".'.format(key))
    return value


def _attribute_term(key, attr, mod, value):
    kind, mods = ATTRIBUTES[attr]
    if mod and mod not in mods:
        raise FilterError('Modifier "{}" is not supported for "{}". Supported: {}.'.format(
            mod, attr, ', '.join(mods)))
    name = attr + ('.' + mod if mod else '')
    if mod in EMPTY_OK_MODS:
        if value:
            raise FilterError('"{}" takes no value; use an empty value.'.format(key))
        return '{}:'.format(name)
    if not value:
        if mod:
            raise FilterError('"{}" needs a value.'.format(key))
        # Bare attribute with no value means "not set" in TaskWarrior.
        return '{}:'.format(name)
    if kind == 'date':
        _check_date(key, value)
    return '{}:"{}"'.format(name, value)


def build_filter_terms(items):
    """Return TaskWarrior filter terms for (key, value) pairs, in request order.

    `items` is typically request.args.items(multi=True). Bare uuid terms are placed
    first, as TaskWarrior expects (same workaround as tasklib's TW-1452 handling).
    Raises FilterError on anything unsupported.
    """
    leading, terms = [], []
    for key, value in items:
        if key.count('.') > 1 or key.endswith('.') or key.startswith('.'):
            raise _unknown(key)
        attr, _, mod = key.partition('.')

        if attr == 'uuid' and mod:
            raise _unknown(key)
        if attr not in SPECIAL and attr not in ATTRIBUTES:
            raise _unknown(key)
        if attr == 'tags' and mod and mod not in ('any', 'none', 'not'):
            raise _unknown(key)

        _check_value(key, value)

        if attr == 'uuid':
            leading.append(_uuid_term(key, value))
        elif attr == 'tags':
            terms.append(_tags_term(key, mod, value))
        else:
            terms.append(_attribute_term(key, attr, mod, value))
    return leading + terms

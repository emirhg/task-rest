import pytest

from task_rest.filters import FilterError, build_filter_terms, supported_names

U = '3f2a9c10-1b2c-4d5e-8f90-a1b2c3d4e5f6'


def terms(*pairs):
    return build_filter_terms(list(pairs))


@pytest.mark.parametrize('pairs, expected', [
    ([], []),
    ([('start.any', '')], ['start.any:']),
    ([('start.none', '')], ['start.none:']),
    ([('start', '')], ['start:']),                       # bare = NOT set in TaskWarrior
    ([('status', 'pending')], ['status:"pending"']),
    ([('status.not', 'completed')], ['status.not:"completed"']),
    ([('project', 'Organizacion.Comunicacion')], ['project:"Organizacion.Comunicacion"']),
    ([('project', 'a b')], ['project:"a b"']),           # one term, spaces kept
    ([('project', "it's")], ['project:"it\'s"']),        # apostrophe is safe in double quotes
    ([('project', 'x:y')], ['project:"x:y"']),           # colon is safe inside quotes
    ([('project.has', 'Com')], ['project.has:"Com"']),
    ([('description.has', 'pandoc')], ['description.has:"pandoc"']),
    ([('due.before', '2030-01-01')], ['due.before:"2030-01-01"']),
    ([('due.after', '2030-01-01T10:30')], ['due.after:"2030-01-01T10:30"']),
    ([('wait.before', 'eod')], ['wait.before:"eod"']),
    ([('start.any', ''), ('status', 'pending')], ['start.any:', 'status:"pending"']),
    ([('tags', 'work')], ['+work']),
    ([('tags.not', 'work')], ['-work']),
    ([('tags.any', '')], ['tags.any:']),
    ([('tags.none', '')], ['tags.none:']),
    ([('tags', 'work'), ('tags', 'home')], ['+work', '+home']),   # repeats are ANDed
    ([('start.any', ''), ('status', 'pending'), ('start', '')], ['start.any:', 'status:"pending"', 'start:']),
    ([('uuid', U)], [U]),
    ([('status', 'pending'), ('uuid', U)], [U, 'status:"pending"']),  # uuid first
])
def test_valid_filters(pairs, expected):
    assert terms(*pairs) == expected


@pytest.mark.parametrize('pairs', [
    [('foo', 'bar')],                       # unknown attribute
    [('id', '1')],                          # deliberately not supported in v1
    [('', 'x')],                            # empty key
    [('start.', '')],                       # dangling dot
    [('.any', '')],                         # leading dot
    [('start.any.x', '')],                  # too many dots
    [('start.before', '')],                 # before needs a value
    [('start.any', '2030-01-01')],          # any takes no value
    [('status.any', '')],                   # status supports only .not
    [('description.any', '')],              # description supports only .not/.has
    [('start.has', 'x')],                   # has is str-only
    [('due', 'notadate')],                  # bad date (TaskWarrior would silently ignore it)
    [('due.before', '2030-13-45')],         # malformed ISO-like date
    [('due.before', '2030-01-01 10:00')],   # space not allowed in date
    [('tags', '')],                         # bare tags needs a name or .any/.none
    [('tags', 'bad tag')],
    [('tags', '-x')],                       # leading dash would be an injected negation
    [('tags.any', 'x')],                    # any takes no value
    [('tags.has', 'x')],                    # unknown tags modifier
    [('uuid', 'not-a-uuid')],
    [('uuid.not', U)],                      # uuid takes no modifier
    [('project', 'x" or project:"y')],      # quote breakout attempt
    [('project', 'x\\')],                   # backslash
    [('project', 'a\nb')],                  # control character
    [('project', 'x' * 257)],               # too long
])
def test_rejected_filters(pairs):
    with pytest.raises(FilterError):
        terms(*pairs)


def test_unknown_error_lists_supported_names():
    with pytest.raises(FilterError) as exc:
        terms(('foo', 'bar'))
    message = str(exc.value)
    assert 'foo' in message
    for name in ('status', 'project', 'start.any', 'tags.not', 'uuid'):
        assert name in message


def test_supported_names_are_stable():
    names = supported_names()
    assert 'start.any' in names and 'tags.any' in names and 'uuid' in names
    assert 'id' not in names

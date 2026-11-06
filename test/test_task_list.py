import json

import pytest
from tasklib import TaskWarrior, Task

def test_get_empty_task_list(client, token):
    rv = client.get('/', headers = {'x-access-tokens': token})
    json_data = rv.get_json()
    assert len(json_data['tasks']) == 0

def test_get_non_empty_task_list(client, tw, token):
    Task(tw, description="Test task").save()
    rv = client.get('/', headers = {'x-access-tokens': token})
    json_data = rv.get_json()
    assert len(json_data['tasks']) == 1

def _post_task(client, token, body):
    return client.post('/', data = json.dumps(body),
                       content_type = 'application/json',
                       headers = {'x-access-tokens': token})

def test_post_empty_task_list(client, token):
    assert len(client.get('/', headers = {'x-access-tokens': token}).get_json()['tasks']) == 0
    rv = _post_task(client, token, {'description': 'first'})
    assert rv.status_code == 200
    assert len(client.get('/', headers = {'x-access-tokens': token}).get_json()['tasks']) == 1

def test_post_single_task_list(client, token):
    rv = _post_task(client, token, {'description': 'single', 'project': 'proj', 'tags': ['a']})
    json_data = rv.get_json()
    assert rv.status_code == 200
    assert json_data['task']['description'] == 'single'
    assert json_data['task']['project'] == 'proj'
    assert json_data['message']['type'] == 'success'

def test_post_multiple_task_list(client, token):
    for name in ('one', 'two', 'three'):
        assert _post_task(client, token, {'description': name}).status_code == 200
    rv = client.get('/', headers = {'x-access-tokens': token})
    assert len(rv.get_json()['tasks']) == 3

def test_post_malformed_task_list(client, token):
    # missing required description
    rv = _post_task(client, token, {'project': 'no-description'})
    assert rv.status_code == 400
    assert rv.get_json()['message']['type'] == 'error'
    # invalid date
    rv = _post_task(client, token, {'description': 'x', 'due': 'not-a-date'})
    assert rv.status_code == 400
    # body is not JSON at all
    rv = client.post('/', data = 'not json', content_type = 'application/json',
                     headers = {'x-access-tokens': token})
    assert rv.status_code == 400
    assert rv.get_json()['message']['type'] == 'error'


# --- attribute filters on GET / (run against real TaskWarrior in the sandbox) ---

def _get_uuids(client, token, query=''):
    rv = client.get('/' + query, headers = {'x-access-tokens': token})
    assert rv.status_code == 200, rv.get_json()
    return sorted(t['uuid'] for t in rv.get_json()['tasks'])

def _seed(tw):
    """Seed a mix of tasks; returns their uuids keyed by a short name."""
    uuids = {}
    t = Task(tw, description='started', project='Org.Com'); t.save(); t.start()
    uuids['started'] = t['uuid']
    t = Task(tw, description='plain'); t.save()
    uuids['plain'] = t['uuid']
    # Seed through execute_command: tasklib's save() mangles a project containing an apostrophe.
    tw.execute_command(['add', 'apostrophe', 'project:"it\'s"'])
    uuids['apostrophe'] = [t['uuid'] for t in tw.tasks.filter('description:apostrophe')][0]
    t = Task(tw, description='spaced', project='a b'); t.save()
    uuids['spaced'] = t['uuid']
    t = Task(tw, description='work+home'); t['tags'] = ['work', 'home']; t.save()
    uuids['work_home'] = t['uuid']
    t = Task(tw, description='work'); t['tags'] = ['work']; t.save()
    uuids['work'] = t['uuid']
    t = Task(tw, description='finished', project='Org.Com'); t.save(); t.done()
    uuids['finished'] = t['uuid']
    return uuids

def test_filter_no_parameters_returns_everything(client, tw, token):
    _seed(tw)
    assert len(_get_uuids(client, token)) == 7

def test_filter_start_any_matches_taskwarrior(client, tw, token):
    uuids = _seed(tw)
    # independent oracle: TaskWarrior's own result for the same filter
    oracle = sorted(t['uuid'] for t in tw.tasks.filter('start.any:'))
    assert _get_uuids(client, token, '?start.any=') == oracle == [uuids['started']]

def test_filter_bare_start_means_not_set(client, tw, token):
    uuids = _seed(tw)
    got = _get_uuids(client, token, '?start=')
    assert uuids['started'] not in got
    assert len(got) == 6

def test_filter_status_and_start_combined(client, tw, token):
    uuids = _seed(tw)
    assert _get_uuids(client, token, '?status=pending&start.any=') == [uuids['started']]

def test_filter_project_with_spaces_and_apostrophe(client, tw, token):
    uuids = _seed(tw)
    assert _get_uuids(client, token, '?project=a%20b') == [uuids['spaced']]
    # tasklib cannot write an apostrophe into project (see REVIEW note), so seed via the CLI
    assert _get_uuids(client, token, '?project=it%27s') == [uuids['apostrophe']]
    assert _get_uuids(client, token, '?project=Org.Com') == sorted(
        [uuids['started'], uuids['finished']])

def test_filter_injection_attempt_is_rejected(client, tw, token):
    _seed(tw)
    # a value that would close the quotes is refused before TaskWarrior runs
    rv = client.get('/?project=x%22%20or%20project%3A%22Org.Com', headers = {'x-access-tokens': token})
    assert rv.status_code == 400
    assert rv.get_json()['message']['type'] == 'error'

def test_filter_tags_are_anded_and_not_works(client, tw, token):
    uuids = _seed(tw)
    assert _get_uuids(client, token, '?tags=work&tags=home') == [uuids['work_home']]
    not_home = _get_uuids(client, token, '?tags.not=home')
    assert uuids['work'] in not_home
    assert uuids['work_home'] not in not_home

def test_filter_uuid(client, tw, token):
    uuids = _seed(tw)
    assert _get_uuids(client, token, '?uuid=' + uuids['plain']) == [uuids['plain']]

def test_filter_dates_use_taskwarrior(client, tw, token):
    uuids = _seed(tw)
    assert _get_uuids(client, token, '?start.before=2000-01-01') == []
    assert uuids['started'] in _get_uuids(client, token, '?start.after=2000-01-01')

def test_filter_unknown_attribute_is_400_and_never_runs_taskwarrior(client, token, monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError('TaskWarrior must not be constructed for an invalid filter')
    monkeypatch.setattr('task_rest.resources.TaskWarrior', boom)
    rv = client.get('/?foo=bar', headers = {'x-access-tokens': token})
    assert rv.status_code == 400
    assert rv.get_json()['message']['type'] == 'error'
    assert 'foo' in rv.get_json()['message']['description']

def test_filter_invalid_date_is_400(client, token):
    rv = client.get('/?due.before=notadate', headers = {'x-access-tokens': token})
    assert rv.status_code == 400
    assert rv.get_json()['message']['type'] == 'error'

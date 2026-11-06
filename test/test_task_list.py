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

import json

import pytest
from tasklib import Task

from task_rest import create_app


@pytest.fixture
def local_client():
    app = create_app(auth_enabled=False, local_only=True)
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def wide_client():
    app = create_app(auth_enabled=False, local_only=False)
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_list_without_token_uses_default_data(local_client, tw):
    Task(tw, description='seeded in default data').save()
    rv = local_client.get('/')
    assert rv.status_code == 200
    assert [t['description'] for t in rv.get_json()['tasks']] == ['seeded in default data']


def test_create_and_modify_without_token(local_client, tw):
    rv = local_client.post('/', data=json.dumps({'description': 'no auth task'}),
                           content_type='application/json')
    assert rv.status_code == 200
    uuid = rv.get_json()['task']['uuid']
    assert [t['uuid'] for t in tw.tasks.all()] == [uuid]

    rv = local_client.put('/{}'.format(uuid), data=json.dumps({'description': 'changed'}),
                          content_type='application/json')
    assert rv.status_code == 200
    assert tw.tasks.get(uuid=uuid)['description'] == 'changed'


def test_token_header_is_ignored_in_local_mode(local_client, tw):
    Task(tw, description='visible').save()
    rv = local_client.get('/', headers={'x-access-tokens': 'garbage'})
    assert rv.status_code == 200
    assert len(rv.get_json()['tasks']) == 1


def test_auth_route_is_absent_in_local_mode(local_client):
    assert local_client.get('/auth').status_code == 404


def test_filters_still_work_in_local_mode(local_client, tw):
    started = Task(tw, description='started'); started.save(); started.start()
    Task(tw, description='plain').save()
    rv = local_client.get('/?start.any=')
    assert rv.status_code == 200
    assert [t['description'] for t in rv.get_json()['tasks']] == ['started']


def test_local_only_rejects_foreign_host_header(local_client, tw):
    Task(tw, description='secret').save()
    rv = local_client.get('/', headers={'Host': 'evil.example'})
    assert rv.status_code == 403
    assert rv.get_json()['message']['type'] == 'error'


def test_local_only_accepts_local_host_headers(local_client, tw):
    Task(tw, description='fine').save()
    for host in ('localhost', 'localhost:5000', '127.0.0.1:5000', '[::1]:5000'):
        rv = local_client.get('/', headers={'Host': host})
        assert rv.status_code == 200, host


def test_wide_local_mode_accepts_any_host_header(wide_client, tw):
    Task(tw, description='lan').save()
    rv = wide_client.get('/', headers={'Host': '192.168.1.5:5000'})
    assert rv.status_code == 200


def test_cors_allows_only_local_origins(local_client, tw):
    Task(tw, description='x').save()
    rv = local_client.get('/', headers={'Origin': 'http://evil.example'})
    assert 'Access-Control-Allow-Origin' not in rv.headers
    rv = local_client.get('/', headers={'Origin': 'http://localhost:3000'})
    assert rv.headers.get('Access-Control-Allow-Origin') == 'http://localhost:3000'


def test_non_uuid_path_never_matches_a_task(local_client, tw):
    # A path segment is a uuid, never a Taskwarrior filter: words must not match descriptions.
    Task(tw, description='pending started').save()
    assert local_client.get('/pending').status_code == 404
    assert local_client.get('/auth').status_code == 404
    assert local_client.delete('/pending').status_code == 404
    assert [t['description'] for t in tw.tasks.all()] == ['pending started']


def test_default_mode_still_requires_token(tw):
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        assert client.get('/').status_code == 401

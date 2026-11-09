import re

import pytest

from task_rest import create_app

BROWSER_ACCEPT = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'


@pytest.fixture
def local_client():
    app = create_app(auth_enabled=False, local_only=True)
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def spec_paths(spec):
    return {p for p in spec['paths']}


def normalize(rule):
    # Flask '/<string:task_uuid>' -> OpenAPI '/{task_uuid}'
    return re.sub(r'<(?:string:)?(\w+)>', r'{\1}', rule)


def test_spec_is_served_without_token_in_local_mode(local_client):
    rv = local_client.get('/docs/openapi.json')
    assert rv.status_code == 200
    assert rv.mimetype == 'application/json'
    assert rv.get_json()['openapi'].startswith('3.')


def test_spec_is_served_without_token_in_authenticated_mode(client):
    rv = client.get('/docs/openapi.json')
    assert rv.status_code == 200
    assert rv.get_json()['info']['title'] == 'task-rest'


def test_docs_respect_local_host_check(local_client):
    rv = local_client.get('/docs/openapi.json', headers={'Host': 'evil.example'})
    assert rv.status_code == 403


def test_browser_gets_the_docs_page_on_root_in_local_mode(local_client):
    rv = local_client.get('/', headers={'Accept': BROWSER_ACCEPT})
    assert rv.status_code == 200
    assert rv.mimetype == 'text/html'
    assert b'docs/openapi.json' in rv.data


def test_browser_gets_the_docs_page_on_root_without_token(client):
    rv = client.get('/', headers={'Accept': BROWSER_ACCEPT})
    assert rv.status_code == 200
    assert rv.mimetype == 'text/html'


def test_api_clients_still_get_json_on_root_in_local_mode(local_client, tw):
    for headers in ({'Accept': '*/*'}, {'Accept': 'application/json'}, {}):
        rv = local_client.get('/', headers=headers)
        assert rv.status_code == 200
        assert rv.mimetype == 'application/json'
        assert 'tasks' in rv.get_json()


def test_api_clients_still_get_401_on_root_in_authenticated_mode(client):
    rv = client.get('/', headers={'Accept': '*/*'})
    assert rv.status_code == 401


def test_spec_paths_match_the_real_routes():
    app = create_app()
    rules = {normalize(r.rule) for r in app.url_map.iter_rules() if r.endpoint != 'static'}
    with app.test_client() as client:
        spec = client.get('/docs/openapi.json').get_json()
    assert spec_paths(spec) == rules

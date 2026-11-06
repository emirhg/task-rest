import pytest
from tasklib import TaskWarrior, Task

# REVIEW: name does not match what the test checks (it verifies that GET / lists one
# seeded task). Rename to something like test_get_lists_seeded_task.
def test_task_done(client, tw, token):
    Task(tw, description="Test task").save()
    rv = client.get('/', headers = {'x-access-tokens': token})
    json_data = rv.get_json()
    assert len(json_data['tasks']) == 1

def test_unknown_command_returns_400(client, token):
    rv = client.put('/00000000-0000-0000-0000-000000000000/bogus',
                    headers = {'x-access-tokens': token})
    assert rv.status_code == 400
    json_data = rv.get_json()
    assert json_data['message']['type'] == 'error'
    assert 'bogus' in json_data['message']['description']

def test_get_unknown_task_returns_404(client, token):
    rv = client.get('/00000000-0000-0000-0000-000000000000',
                    headers = {'x-access-tokens': token})
    assert rv.status_code == 404
    assert rv.get_json()['message']['type'] == 'error'

def test_dependency_on_unknown_task_returns_404(client, tw, token):
    task = Task(tw, description="Test task")
    task.save()
    rv = client.put('/{}/add_dependency'.format(task['uuid']),
                    json={'uuid': '00000000-0000-0000-0000-000000000000'},
                    headers = {'x-access-tokens': token})
    assert rv.status_code == 404
    assert rv.get_json()['message']['type'] == 'error'

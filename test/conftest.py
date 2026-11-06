import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ['FLASK_ENV'] = "development"

import pytest

from task_rest import create_app
from tasklib import TaskWarrior
import jwt
from datetime import datetime, timedelta


@pytest.fixture(autouse=True)
def isolated_taskwarrior(tmpdir, monkeypatch):
    """Never let the suite read or write the real ~/.taskrc or ~/.task.

    HOME, TASKRC and TASKDATA all point into this test's tmpdir, so even code that
    does not pass explicit paths only sees the sandbox.
    """
    home = tmpdir.mkdir('home')
    home.ensure('taskrc')
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setenv('TASKRC', str(home.join('taskrc')))
    monkeypatch.setenv('TASKDATA', str(tmpdir.join('task')))


@pytest.fixture
def taskrc(tmpdir):
    return str(tmpdir.join('home', 'taskrc'))


@pytest.fixture
def taskdata(tmpdir):
    return str(tmpdir.join('task'))


@pytest.fixture
def client(tmpdir, taskrc, taskdata):
    app = create_app()
    app.config['TESTING'] = True
    app.config['USER_CONF']['dev']['TASKDATA_LOCATION'] = taskdata
    app.config['USER_CONF']['dev']['TASKRC_LOCATION'] = taskrc

    with app.test_client() as client:
        yield client

@pytest.fixture
def tw(taskrc, taskdata):
    """TaskWarrior bound to the same sandboxed data and taskrc the app uses."""
    return TaskWarrior(data_location=taskdata, taskrc_location=taskrc)

@pytest.fixture
def token():
    token = jwt.encode({
        'public_id': 'dev',
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() \
        + timedelta(minutes=6)
    }, 'SECRET_KEY', algorithm="HS256")
    return token

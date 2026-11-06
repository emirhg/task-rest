import pytest

from task_rest import serve


@pytest.mark.parametrize('host', ['127.0.0.1', '127.0.0.5', '::1', '[::1]', 'localhost'])
def test_loopback_hosts(host):
    assert serve.is_loopback(host)


@pytest.mark.parametrize('host', ['0.0.0.0', '::', '192.168.1.5', 'example.com', ''])
def test_non_loopback_hosts(host):
    assert not serve.is_loopback(host)


class Recorder:
    def __init__(self, answer=None, tty=True):
        self.answer = answer
        self.tty = tty
        self.prompts = 0

    def input_fn(self, prompt):
        self.prompts += 1
        return self.answer

    def isatty(self):
        return self.tty


def test_confirm_refuses_without_terminal_and_never_prompts():
    rec = Recorder(answer='yes', tty=False)
    with pytest.raises(SystemExit) as exc:
        serve.confirm_exposure('0.0.0.0', 5000, input_fn=rec.input_fn, isatty=rec.isatty)
    assert exc.value.code == 2
    assert rec.prompts == 0


@pytest.mark.parametrize('answer', ['no', '', 'y', 'Yes', 'yes '])
def test_confirm_rejects_anything_but_exact_yes(answer):
    rec = Recorder(answer=answer)
    with pytest.raises(SystemExit) as exc:
        serve.confirm_exposure('0.0.0.0', 5000, input_fn=rec.input_fn, isatty=rec.isatty)
    assert exc.value.code == 1
    assert rec.prompts == 1


def test_confirm_accepts_exact_yes():
    rec = Recorder(answer='yes')
    serve.confirm_exposure('0.0.0.0', 5000, input_fn=rec.input_fn, isatty=rec.isatty)
    assert rec.prompts == 1


def _run_main(argv, answer=None, tty=True, monkeypatch=None):
    calls = {'create': [], 'run': []}
    rec = Recorder(answer=answer, tty=tty)

    def fake_create_app(**kwargs):
        calls['create'].append(kwargs)
        return 'APP'

    monkeypatch.setattr(serve, 'create_app', fake_create_app)

    def fake_run(app, host, port):
        calls['run'].append((app, host, port))

    serve.main(argv, input_fn=rec.input_fn, isatty=rec.isatty, run=fake_run)
    return calls, rec


def test_default_is_auth_on_loopback(monkeypatch):
    calls, rec = _run_main([], monkeypatch=monkeypatch)
    assert calls['create'] == [{'auth_enabled': True}]
    assert calls['run'] == [('APP', '127.0.0.1', 5000)]
    assert rec.prompts == 0


def test_default_auth_on_wide_bind_does_not_prompt(monkeypatch):
    calls, rec = _run_main(['--host', '0.0.0.0'], monkeypatch=monkeypatch)
    assert calls['create'] == [{'auth_enabled': True}]
    assert rec.prompts == 0


def test_no_auth_loopback_does_not_prompt(monkeypatch):
    calls, rec = _run_main(['--no-auth'], monkeypatch=monkeypatch)
    assert calls['create'] == [{'auth_enabled': False, 'local_only': True}]
    assert calls['run'] == [('APP', '127.0.0.1', 5000)]
    assert rec.prompts == 0


def test_no_auth_ipv6_loopback_is_local_only(monkeypatch):
    calls, _ = _run_main(['--no-auth', '--host', '::1'], monkeypatch=monkeypatch)
    assert calls['create'] == [{'auth_enabled': False, 'local_only': True}]


def test_no_auth_wide_bind_prompts_and_starts_when_confirmed(monkeypatch):
    calls, rec = _run_main(['--no-auth', '--host', '0.0.0.0', '--port', '8080'],
                           answer='yes', monkeypatch=monkeypatch)
    assert rec.prompts == 1
    assert calls['create'] == [{'auth_enabled': False, 'local_only': False}]
    assert calls['run'] == [('APP', '0.0.0.0', 8080)]


def test_no_auth_wide_bind_declined_never_creates_app_or_binds(monkeypatch):
    created = []
    monkeypatch.setattr(serve, 'create_app', lambda **kw: created.append(kw))
    with pytest.raises(SystemExit) as exc:
        serve.main(['--no-auth', '--host', '0.0.0.0'],
                   input_fn=lambda p: 'no', isatty=lambda: True,
                   run=lambda *a: created.append('run'))
    assert exc.value.code == 1
    assert created == []


def test_no_auth_wide_bind_without_terminal_refuses(monkeypatch):
    created = []
    monkeypatch.setattr(serve, 'create_app', lambda **kw: created.append(kw))
    with pytest.raises(SystemExit) as exc:
        serve.main(['--no-auth', '--host', '192.168.1.5'],
                   input_fn=lambda p: 'yes', isatty=lambda: False,
                   run=lambda *a: created.append('run'))
    assert exc.value.code == 2
    assert created == []


def test_run_always_disables_debugger(monkeypatch):
    seen = {}

    class FakeApp:
        def run(self, **kwargs):
            seen.update(kwargs)

    monkeypatch.setattr(serve, 'create_app', lambda **kw: FakeApp())
    serve.main([])  # real default run() path
    assert seen['debug'] is False
    assert seen['host'] == '127.0.0.1'

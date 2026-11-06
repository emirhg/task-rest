"""Start the task-rest server.

    python -m task_rest.serve                          # authentication on, 127.0.0.1:5000
    python -m task_rest.serve --no-auth                # local mode: no auth, loopback only
    python -m task_rest.serve --no-auth --host 0.0.0.0 # warns and asks for confirmation

Local mode (--no-auth) uses the running user's Taskwarrior defaults ($TASKDATA/$TASKRC or
~/.task, ~/.taskrc). It is the only way to start without auth: `flask run` and the WSGI
entry point always keep authentication on.
"""
import argparse
import getpass
import ipaddress
import os
import sys

from task_rest import create_app

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 5000

EXPOSURE_WARNING = """
!!! WARNING: UNAUTHENTICATED API EXPOSED TO THE NETWORK !!!
You asked to run WITHOUT authentication on {host}:{port}, which is not a loopback address.
Anyone who can reach {host}:{port} can read, create, change, delete and sync ALL Taskwarrior
tasks of the user running this server ({user}). Browser protections (CORS, Host checks) do
not stop other machines or scripts from calling it.
Only continue if this network is fully trusted and you accept that risk.
"""


def is_loopback(host):
    """True for localhost and loopback IP addresses (127.0.0.0/8, ::1)."""
    if host == 'localhost':
        return True
    try:
        return ipaddress.ip_address(host.strip('[]')).is_loopback
    except ValueError:
        return False


def confirm_exposure(host, port, input_fn=input, isatty=None):
    """Warn and require the exact answer 'yes' before a non-loopback no-auth start.

    Without a terminal there is nobody to confirm, so the server refuses to start.
    """
    isatty = isatty or sys.stdin.isatty
    user = getpass.getuser()
    sys.stderr.write(EXPOSURE_WARNING.format(host=host, port=port, user=user))
    if not isatty():
        sys.stderr.write('Refusing to start: no terminal to confirm the risk. Run this from an '
                         'interactive shell, or use authentication.\n')
        raise SystemExit(2)
    answer = input_fn("Type 'yes' to expose the unauthenticated API on {}: ".format(host))
    if answer != 'yes':
        sys.stderr.write('Not started.\n')
        raise SystemExit(1)


def _banner(host, port):
    sys.stderr.write(
        'task-rest: AUTHENTICATION DISABLED (local mode). Listening on {}:{}.\n'
        '  Taskwarrior data: TASKDATA={} (default ~/.task)\n'
        '  Taskwarrior rc:   TASKRC={} (default ~/.taskrc)\n'.format(
            host, port,
            os.environ.get('TASKDATA', '<unset>'),
            os.environ.get('TASKRC', '<unset>')))


def main(argv=None, input_fn=input, isatty=None, run=None):
    parser = argparse.ArgumentParser(description='Run the task-rest API server.')
    parser.add_argument('--no-auth', action='store_true',
                        help='disable authentication and use the current user\'s Taskwarrior '
                             'data (local use; non-loopback hosts need confirmation)')
    parser.add_argument('--host', default=DEFAULT_HOST,
                        help='address to bind (default: %(default)s)')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT,
                        help='port to bind (default: %(default)s)')
    args = parser.parse_args(argv)

    if args.no_auth:
        if not is_loopback(args.host):
            # Confirm BEFORE creating the app or opening any socket.
            confirm_exposure(args.host, args.port, input_fn=input_fn, isatty=isatty)
        local_only = is_loopback(args.host)
        app = create_app(auth_enabled=False, local_only=local_only)
        _banner(args.host, args.port)
    else:
        app = create_app(auth_enabled=True)

    if run is None:
        def run(app, host, port):
            app.run(host=host, port=port, debug=False)  # the debugger must never be exposed
    run(app, args.host, args.port)
    return 0


if __name__ == '__main__':
    sys.exit(main())

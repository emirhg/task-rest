# task-rest
Restful API for taskwarrior built with flask and tasklib.

## Dependancies
* python3
* pipenv
* [taskwarrior](https://github.com/GothenburgBitFactory/taskwarrior) 3.0 or newer (the tasklib fork in the Pipfile refuses 2.x)
### Python dependancies (see Pipfile)
* flask
* flask-restful
* flask-cors
* marshmallow
* tasklib
* pyjwt

## Quick start

### 1. Prerequisites
- Python 3.14 and `pipenv` (or `pipx`, see "Install with pipx" below).
- Taskwarrior 3.0 or newer: `task --version`.
- A Taskwarrior config file. If you have never used Taskwarrior, create an empty one:
  `touch ~/.taskrc`. Without it every request fails with "Cannot proceed without rc file.".

### 2. Install
    git clone https://github.com/emirhg/task-rest.git
    cd task-rest
    pipenv install

#### Install with pipx (alternative)
pipx installs the project as a `task-rest` command in its own environment. Use Python 3.14 or
newer (pipx picks the default interpreter; add `--python <path>` if that is older):

    pipx install /path/to/task-rest      # or: pipx install git+https://github.com/emirhg/task-rest.git
    task-rest --no-auth                  # same as: pipenv run serve_local

### 3. Start without authentication (simplest)
This mode uses your own Taskwarrior data (`~/.task` and `~/.taskrc`) and listens on
`127.0.0.1` only. See "Running without authentication" below for the safety rules.

    pipenv run serve_local

The server prints a banner and then listens on http://127.0.0.1:5000. In another terminal:

    # create a task; the response contains its "uuid"
    curl -s -X POST http://127.0.0.1:5000/ -H 'Content-Type: application/json' \
         -d '{"description": "Write README", "project": "docs", "tags": ["work"]}'

    # list pending tasks
    curl -s 'http://127.0.0.1:5000/?status=pending'

    # start and complete it (replace UUID with the uuid from the response)
    curl -s -X PUT http://127.0.0.1:5000/UUID/start
    curl -s -X PUT http://127.0.0.1:5000/UUID/done

    # only tasks that have been started
    curl -s 'http://127.0.0.1:5000/?status=pending&start.any='

Paths take the task's uuid, not its numeric id (`/1/start` returns 404). Stop the server with Ctrl+C.

To try it on throwaway data first, point Taskwarrior at a temporary directory:

    mkdir -p /tmp/task-rest-demo && touch /tmp/task-rest-demo/taskrc
    TASKDATA=/tmp/task-rest-demo TASKRC=/tmp/task-rest-demo/taskrc pipenv run serve_local

### 4. Start with authentication (several users, separate data)
One-time setup. `add_user` needs `instance/config.json` to exist:

    mkdir -p instance && echo '{}' > instance/config.json
    pipenv run add_user

Answer the prompts. For the taskdata and taskrc locations, enter explicit paths such as
`/home/you/.task` and `/home/you/.taskrc`. Leaving them blank stores no paths for the user,
and every request then fails with a server error (known issue, see the BUG notes in
`task_rest/resources.py`).

Start the server (the app must be named with `FLASK_APP`):

    FLASK_APP=task_rest pipenv run flask run

Get a token with the username and password you chose, then send it in the
`x-access-tokens` header:

    curl -s -u alice:YOUR_PASSWORD http://127.0.0.1:5000/auth
    # {"token": "..."}
    curl -s http://127.0.0.1:5000/ -H 'x-access-tokens: TOKEN'

Tokens are invalidated when the server restarts (the signing key is generated per process).

A built-in demo user `dev` with password `password` is available in development mode. Its data is
kept in `instance/dev/`. Do not use it outside of trying the API:

    FLASK_APP=task_rest FLASK_ENV=development pipenv run flask run
    curl -s -u dev:password http://127.0.0.1:5000/auth

For deploying the Flask app see https://flask.palletsprojects.com/en/stable/deploying/.

## Running without authentication (local mode)
Taskwarrior has no users, so a single-user machine can run the API without tokens. Local mode
uses the running user's Taskwarrior defaults (`$TASKDATA`/`$TASKRC`, or `~/.task` and `~/.taskrc`).

    pipenv run serve_local          # == python -m task_rest.serve --no-auth
    python -m task_rest.serve --no-auth --port 5001

- Authentication is only disabled by this explicit `--no-auth` flag. `flask run` and the WSGI
  entry point always keep it on.
- Bound to a loopback address (`127.0.0.1`, `localhost`, `::1`, the default), local mode:
  - accepts requests only with a local `Host` header (blocks DNS rebinding);
  - allows browser calls only from `localhost`, `127.0.0.1` and `[::1]` origins (CORS).
- Bound to any other address (`0.0.0.0`, a LAN address, ...), the server prints a risk warning
  and requires you to type `yes`. Without a terminal it refuses to start. Anyone who can reach
  the address can read and change all of your tasks, and browser protections do not stop them.
- The `/auth` route does not exist in local mode.

## Testing
    pipenv install --dev
    pipenv run tests

The tests run against Taskwarrior in a temporary data directory and do not touch your own tasks.

## Schemas
```
taskAnnotation {
    "description": string,

    # read-only
    "entry": date
}

task {
    "description": string,
    "due": date,
    "priority": string,
    "project": string,
    "recur": string,
    "scheduled": date,
    "start": date,
    "tags": list(strings)
    "until": date,

    # read-only
    "annotations": list[taskAnnotation],
    "depends": list[task],
    "end": date,
    "entry": date,
    "id": int,
    "imask": int,
    "mask": string,
    "modified": date,
    "parent": task,
    "status": string,
    "urgency": float,
    "uuid": string
}
```

## API
### Documentation
The API is documented as an OpenAPI 3 document, served without authentication in every mode:

- `GET /docs/openapi.json`: the machine-readable spec (`task_rest/docs/openapi.json`).
- `GET /` in a browser (a request that prefers `text/html`): a page that renders the spec.
  API clients (`curl`, scripts, requests without an `Accept: text/html` header) still get the
  JSON task list from `GET /`.

    curl -s http://127.0.0.1:5000/docs/openapi.json

### `/auth` endpoint
#### GET
With correct username and password as basic authentication headers.
#### Response
JWT required for all other requests.
```
{
  "token": JWT
}
```
`x-access-tokens` must be set to JWT for all other endpionts.

### `/` endpoint
#### GET
Get list of tasks. Without parameters, all tasks are returned (including completed and deleted ones).

Query parameters filter the list with TaskWarrior itself, using the TaskWarrior attribute names:

| Parameter | Meaning (TaskWarrior equivalent) |
|-----------|----------------------------------|
| `status=pending` | `status:pending` |
| `status.not=completed` | `status.not:completed` |
| `project=NAME`, `project.has=X`, `project.not=X`, `project.any=`, `project.none=` | `project:"NAME"` and so on |
| `priority=H`, `priority.not=L`, `priority.any=`, `priority.none=` | `priority:H` and so on |
| `description.has=X`, `description.not=X` | `description.has:"X"` and so on |
| `tags=work` | `+work` |
| `tags.not=work` | `-work` |
| `tags.any=`, `tags.none=` | `tags.any:`, `tags.none:` |
| `uuid=UUID` | the task with that uuid |
| `start`, `due`, `scheduled`, `wait`, `entry`, `end` with `=DATE` | `attr:"DATE"` |
| `start.before=DATE`, `start.after=DATE`, `start.not=DATE` | `start.before:"DATE"` and so on |
| `start.any=`, `start.none=` | `start.any:`, `start.none:` |

- A bare attribute with an empty value (`start=`) means the attribute is **not set**, exactly as in TaskWarrior. Use `start.any=` for "is set".
- `DATE` is `YYYY-MM-DD`, `YYYY-MM-DDTHH:MM[:SS][Z]`, or one of `now`, `today`, `sod`, `eod`, `yesterday`, `tomorrow`, `sow`, `eow`, `som`, `eom`, `soy`, `eoy`.
- Parameters are combined with AND. Repeating a parameter adds another term (`?tags=work&tags=home` means `+work +home`).
- Values may not contain `"`, `\`, or control characters (400). Values are passed to TaskWarrior as single arguments, never through a shell.
- An unknown attribute or modifier, an invalid date, or a malformed value returns `400` with a message. `id` is not supported (it is not stable across changes).

Example: `GET /?status=pending&start.any=` returns the pending tasks that have been started.
#### Response
```
{
  "tasks": [
    LIST OF ALL TASKS
  ]
}
```
#### POST
Add a new task.
Body:
```
{
# required
  "description": "DESCRIPTION",

# optional
  "due": date,
  "project": "PROJECT",
  "tags": ["TAG_1", "TAG_2"]
# BUG: "hide" is not a field in TaskSchema (task_rest/schemas.py), so it is silently dropped.
  "hide": date,
  "scheduled": date,
  "start": date
}
```

<!-- TODO: GET, PUT and DELETE for this endpoint are not documented yet. -->
### `/<string:uuid>` endpoint
#### GET
#### PUT
#### DELETE

<!-- TODO: document the valid commands (done, restore, start, stop, add_annotation,
remove_annotation, add_dependency, remove_dependency) and the GET /sync endpoint, which is
not documented at all. -->
## `/<string:task_uuid>/<string:command>` endpoint
#### PUT

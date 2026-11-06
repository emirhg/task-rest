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

## Setup
Run `pipenv install` to install all python dependencies.
Then `pipenv run add_user` and follow the instruction to configure a user.
Test the server in development mode with `pipenv run serve`.
See https://flask.palletsprojects.com/en/2.0.x/deploying/index.html for information on deploying flask apps.

## Testing
`pipenv run tests` runs the test suite.

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

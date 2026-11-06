from functools import wraps
from flask import current_app
from flask import jsonify, request, make_response
from flask_restful import Resource
from marshmallow import ValidationError
from tasklib import TaskWarrior, Task
from tasklib.backends import TaskWarriorException
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta
import json
import jwt

from task_rest.schemas import TaskSchema, TaskAnnotationSchema, DependantTaskSchema
from task_rest.filters import FilterError, build_filter_terms, is_uuid

ts = TaskSchema(unknown='EXCLUDE')
tas = TaskAnnotationSchema(unknown='EXCLUDE')
dts = DependantTaskSchema(unknown='EXCLUDE')

VALID_COMMANDS = ('done', 'restore', 'start', 'stop', 'add_annotation',
                  'remove_annotation', 'add_dependency', 'remove_dependency')


def token_required(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        # Local mode (create_app(auth_enabled=False)): no user, any token header is ignored.
        if not current_app.config.get('AUTH_ENABLED', True):
            return f(None, *args, **kwargs)
        token = None
        try:
            token = request.headers['x-access-tokens']
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms="HS256")
            user = data['public_id']
        except Exception as e:
            return make_response('Could not verify', 401, {'WWW.Authentification': 'Basic realm: "{}"'.format(e)})

        return f(user, *args, **kwargs)
    return decorator

def error_response(description, status):
    return make_response(jsonify({'message': {
        'description': description,
        'type': 'error'
    }}), status)

def expose_errors(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        try:
            result = f(*args, **kwargs)
        # BUG: TaskWarriorException is returned as HTTP 200 with an error body (e.g. /sync
        # without a configured server). Should use an error status; left unchanged so
        # existing clients keep working.
        except TaskWarriorException as e:
            error = '\n'.join([x for x in str(e).split('\n') if not (
                x.startswith("Configuration override")
                or x.startswith("Command used")
                or x.startswith("TASKRC")
                or x.startswith("TASKDATA")
            )])
            result = jsonify({'message': {
                'description': error,
                'type': 'error'
            }})
        except ValidationError as e:
            result = error_response('Invalid input: ' + json.dumps(e.messages), 400)
        except json.JSONDecodeError as e:
            result = error_response('Malformed JSON body: ' + str(e), 400)
        except Task.DoesNotExist as e:
            result = error_response(str(e), 404)
        except FilterError as e:
            result = error_response(str(e), 400)
        return result
    return decorator

# REVIEW: task['id'] is documented as 0 for completed/deleted tasks. Not reproduced on
# Taskwarrior 3.5.0 (the 'Completed task N.' message showed the real id). Verify before
# relying on the id in messages.
def json_task_and_message(task, message, msg_type):
    return jsonify({
        'task': ts.dump(task),
        'message': {
            'description': message.format(task['id']),
            'type': msg_type
        }
    })

def get_task(tw, task_uuid):
    """Look a task up by uuid only.

    tasklib's uuid lookup passes its value into Taskwarrior's filter list, so a
    non-uuid path segment such as 'pending' would match descriptions. Anything that is
    not a uuid is treated as "no such task" (404).
    """
    if not is_uuid(task_uuid):
        raise Task.DoesNotExist('No task with uuid "{}".'.format(task_uuid))
    return tw.tasks.get(uuid=task_uuid)


def tw_for_user(user):
    if user is None:
        # Local mode: no explicit paths, so Taskwarrior uses $TASKDATA/$TASKRC or the
        # running user's ~/.task and ~/.taskrc.
        return TaskWarrior()
    return TaskWarrior(
        data_location=current_app.config['USER_CONF'][user]['TASKDATA_LOCATION'],
        # BUG: TASKRC_LOCATION is optional in scripts/add_user.py, but read here
        # unconditionally. A user without it raises KeyError (HTTP 500).
        taskrc_location=current_app.config['USER_CONF'][user]['TASKRC_LOCATION']
    )


class TaskResource(Resource):
    method_decorators = [token_required, expose_errors]
    def get(self, user, task_uuid):
        tw = tw_for_user(user)
        task = get_task(tw, task_uuid)
        return jsonify({'task': ts.dump(task)})

    # task modify
    def put(self, user, task_uuid):
        tw = tw_for_user(user)
        task = get_task(tw, task_uuid)
        data = ts.loads(request.data)
        for key in data:
            task[key] = data[key]
        task.save()
        return json_task_and_message(task, 'Modified task {}.', 'success')

    # task delete
    def delete(self, user, task_uuid):
        tw = tw_for_user(user)
        task = get_task(tw, task_uuid)
        task.delete()
        return json_task_and_message(task, 'Deleted task {}.', 'info')


class TaskListResource(Resource):
    method_decorators = [token_required, expose_errors]
    def get(self, user):
        # Validate filters before tw_for_user(): an invalid request must not spawn `task`.
        terms = build_filter_terms(request.args.items(multi=True))
        tw = tw_for_user(user)
        # REVIEW: on Taskwarrior 3.5.0 a recurring task (recur + due) was listed twice
        # (template and instance?). Not verified whether this is expected.
        tasks = tw.tasks.filter(*terms) if terms else tw.tasks.all()
        return jsonify({'tasks': ts.dump(tasks, many=True)})

    # BUG: tasklib save() writes a project containing an apostrophe incorrectly: the task
    # is created with description "project:'it's'" and no project (observed on TW 3.5.0).
    # Affects this endpoint too. Needs a fix in the tasklib fork (quote values on add).
    def post(self, user):
        tw = tw_for_user(user)
        task = Task(tw)
        data = ts.loads(request.data)
        for key in data:
            task[key] = data[key]
        task.save()
        return json_task_and_message(task, 'Added task {}.', 'success')


class TaskCommandResource(Resource):
    method_decorators = [token_required, expose_errors]
    def put(self, user, task_uuid, command):
        if command not in VALID_COMMANDS:
            return error_response('Unknown command "{}". Valid commands: {}.'.format(
                command, ', '.join(VALID_COMMANDS)), 400)
        tw = tw_for_user(user)
        task = get_task(tw, task_uuid)
        if command == 'done':
            msg = 'Completed task {}.'
            task.done()
        elif command == 'restore':
            msg = 'Restored task {}.'
            task['status'] = 'pending'
            task.save()
        elif command == 'start':
            msg = 'Started task {}.'
            task.start()
        elif command == 'stop':
            msg = 'Stopped task {}.'
            task.stop()
        elif command == 'add_annotation':
            msg = 'Added annotation to task {}.'
            data = tas.loads(request.data)
            task.add_annotation(data["description"])
        elif command == 'remove_annotation':
            msg = 'Removed annotaion from task {}'
            data = tas.loads(request.data)
            task.remove_annotation(data["description"])
        elif command == 'add_dependency':
            msg = 'Added dependency to task {}'
            data = dts.loads(request.data)
            dep = get_task(tw, data['uuid'])
            task['depends'].add(dep)
            task.save()
        elif command == 'remove_dependency':
            msg = 'Removed dependency to task {}'
            data = dts.loads(request.data)
            dep = get_task(tw, data['uuid'])
            task['depends'].remove(dep)
            task.save()
        # REVIEW: msg is only bound inside the if/elif branches. The VALID_COMMANDS guard
        # above makes the fall-through unreachable, but the dispatch is fragile.
        # TODO: replace the if/elif chain with a dict of command -> (action, message).
        return json_task_and_message(task, msg, 'info')


class TaskServerResource(Resource):
    method_decorators = [token_required, expose_errors]
    def get(self, user):
        tw = tw_for_user(user)
        # BUG: a sync failure is reported as HTTP 200 via expose_errors (see above).
        tw.sync()
        return jsonify({
            'message': {
                'description': 'Sync successful.',
                'type': 'info'
            }
        })


class AuthResource(Resource):
    def get(self):
        auth = request.authorization
        if auth and \
            auth.username and \
            auth.password and \
            auth.username in current_app.config['USER_CONF'] and \
            check_password_hash(current_app.config['USER_CONF'][auth.username]['PASSWORD'], auth.password):

            token = jwt.encode({
                'public_id': auth.username,
                'iat': datetime.utcnow(),
                'exp': datetime.utcnow() + timedelta(minutes=current_app.config['USER_CONF'][auth.username]['TOKEN_EXP'])
            }, current_app.config['SECRET_KEY'], algorithm="HS256")
            return jsonify({'token': token})
        return make_response('Could not verify', 401, {'WWW.Authentification': 'Basic realm: "login required"'})

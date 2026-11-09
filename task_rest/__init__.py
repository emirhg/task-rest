import os
import re

from flask import Flask, jsonify, make_response, request
from flask_cors import CORS
from flask_restful import Api
from tasklib import TaskWarrior

from task_rest.config import Config, ProductionConfig, DevelopmentConfig
from task_rest.resources import (TaskResource, TaskListResource,
                                 TaskCommandResource, TaskServerResource,
                                 AuthResource)

from os.path import join

# Local mode: only browsers on the same machine may call the API (CORS).
LOCAL_ORIGIN_RE = re.compile(r'^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$')
# Local mode bound to loopback: only these Host headers are accepted (blocks DNS rebinding).
LOCAL_HOST_RE = re.compile(r'^(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$')

def create_app(auth_enabled=True, local_only=False):
    """Create the API.

    auth_enabled=True (default): every route except /auth requires a JWT; the user
    picks TASKDATA/TASKRC from instance/config.json.

    auth_enabled=False: no authentication and no /auth route. Tasks are read from the
    running user's Taskwarrior defaults ($TASKDATA/$TASKRC or ~/.task, ~/.taskrc).
    Only meant for local use; see task_rest.serve, which enforces the loopback rules.
    local_only=True additionally rejects requests whose Host header is not local.
    """
    app = Flask(__name__, instance_relative_config=True)
    app.config['AUTH_ENABLED'] = auth_enabled

    if auth_enabled:
        # app.config["ENV"] was removed in Flask 2.3; read FLASK_ENV directly (default: production).
        if os.environ.get("FLASK_ENV", "production") == "production":
            app.config.from_object(ProductionConfig())
        else:
            app.config.from_object(DevelopmentConfig())
        CORS(app)
    else:
        app.config.from_object(Config)
        app.config['USER_CONF'] = {}
        CORS(app, origins=[LOCAL_ORIGIN_RE])
        if local_only:
            @app.before_request
            def reject_non_local_host():
                if not LOCAL_HOST_RE.match(request.host):
                    return make_response(jsonify({'message': {
                        'description': 'Forbidden: this server only accepts local Host headers.',
                        'type': 'error'
                    }}), 403)

    api = Api(app)
    if auth_enabled:
        api.add_resource(AuthResource, '/auth')
    api.add_resource(TaskListResource, '/')
    api.add_resource(TaskResource, '/<string:task_uuid>')
    api.add_resource(TaskServerResource, '/sync')
    api.add_resource(TaskCommandResource, '/<string:task_uuid>/<string:command>')

    return app

from flask import Flask
from os import urandom
from os.path import join
import json
from werkzeug.security import generate_password_hash

app = Flask(__name__, instance_relative_config=True)
class Config(object):
    """Base config."""
    DEBUG = False
    TESTING = False


class ProductionConfig(Config):
    # BUG: SECRET_KEY is regenerated on every process start, so tokens are invalidated
    # on restart and differ between worker processes. Persist it in instance/config.json.
    SECRET_KEY = urandom(16)
    USER_CONF = {}
    def __init__(self):
        with app.open_instance_resource('config.json') as f:
            self.USER_CONF = json.load(f)


class DevelopmentConfig(Config):
    DEBUG = True
    SECRET_KEY = 'SECRET_KEY'
    USER_CONF = {
        "dev": {
            "TOKEN_EXP": 999,
            # TODO: method='sha256' is not accepted by Werkzeug 3; move to scrypt/pbkdf2
            # and regenerate stored password hashes when porting to Werkzeug 3.
            "PASSWORD": generate_password_hash('password', method='sha256'),
            "CORS_ORIGINS": '*',
            "TASKDATA_LOCATION": join(app.instance_path, "dev", ".task"),
            "TASKRC_LOCATION": join(app.instance_path, "dev", ".taskrc")
        }
    }

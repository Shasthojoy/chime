from os import environ
from flask import Blueprint, current_app, Flask
from logging import getLogger, DEBUG

bizarro = Blueprint('bizarro', __name__, template_folder='templates')

def create_app():
    app = Flask(__name__, static_folder='static')
    app.secret_key = 'boop'
    app.config['WORK_PATH'] = environ.get('WORK_PATH', '.')
    app.config['REPO_PATH'] = environ.get('REPO_PATH', 'sample-site')
    app.config['BROWSERID_URL'] = environ.get('BROWSERID_URL', 'http://127.0.0.1:5000')
    app.config['SINGLE_USER'] = bool(environ.get('SINGLE_USER', False))
    app.config['default_branch'] = 'master'

    # attach routes and custom error pages here
    app.register_blueprint(bizarro)

    return app

# @app.before_first_request
# def before_first_request():
#     '''
#     '''
#     if current_app.debug:
#         getLogger('bizarro').setLevel(DEBUG)

from . import views


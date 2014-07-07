from os import environ
from flask import Flask

from . import repo_functions, edit_functions, jekyll_functions

app = Flask(__name__)
app.secret_key = 'boop'
app.config['WORK_PATH'] = environ.get('WORK_PATH', '.')
app.config['REPO_PATH'] = environ.get('REPO_PATH', 'sample-site')
app.config['default_branch'] = 'master'

from . import views

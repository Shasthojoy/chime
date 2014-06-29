from os import environ
from flask import Flask
from . import repo, edit

app = Flask(__name__)
app.secret_key = 'boop'
app.config['WORK_PATH'] = '.'
app.config['REPO_PATH'] = environ.get('REPO_PATH', 'sample-site')

from . import views

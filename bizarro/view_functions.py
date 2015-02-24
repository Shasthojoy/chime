from logging import getLogger
Logger = getLogger('bizarro.view_functions')

from os.path import join, isdir, realpath, basename, dirname
from os import listdir, environ
from urllib import quote, unquote
from urlparse import urljoin, urlparse
from mimetypes import guess_type
from functools import wraps
from io import BytesIO
import csv, re

from git import Repo
from flask import request, session, current_app, redirect
from requests import get

from .repo_functions import start_branch
from .href import needs_redirect, get_redirect

from fcntl import flock, LOCK_EX, LOCK_UN, LOCK_SH

class WriteLocked:
    ''' Context manager for a locked file open in a+ mode, seek(0).
    '''
    def __init__(self, fname):
        self.fname = fname
        self.file = None

    def __enter__(self):
        self.file = open(self.fname, 'a+')
        flock(self.file, LOCK_EX)
        self.file.seek(0)
        return self.file

    def __exit__(self, *args):
        flock(self.file, LOCK_UN)
        self.file.close()

class ReadLocked:
    ''' Context manager for a locked file open in r mode, seek(0).
    '''
    def __init__(self, fname):
        self.fname = fname
        self.file = None

    def __enter__(self):
        self.file = open(self.fname, 'r')
        flock(self.file, LOCK_SH)
        return self.file

    def __exit__(self, *args):
        flock(self.file, LOCK_UN)
        self.file.close()

def dos2unix(string):
    ''' Returns a copy of the strings with line-endings corrected.
    '''
    return string.replace('\r\n', '\n').replace('\r', '\n')

def get_repo(flask_app):
    ''' Gets repository for the current user, cloned from the origin.

        Uses the first-ever commit in the origin repository to name
        the cloned directory, to reduce history conflicts when tweaking
        the repository during development.
    '''
    source_repo = Repo(flask_app.config['REPO_PATH'])
    first_commit = list(source_repo.iter_commits())[-1].hexsha
    dir_name = 'repo-{}-{}'.format(first_commit[:8], session.get('email', 'nobody'))
    user_dir = realpath(join(flask_app.config['WORK_PATH'], quote(dir_name)))

    if isdir(user_dir):
        user_repo = Repo(user_dir)
        user_repo.git.reset(hard=True)
        user_repo.remotes.origin.fetch()
    else:
        user_repo = source_repo.clone(user_dir, bare=False)

    return user_repo

def name_branch(description):
    ''' Generate a name for a branch from a description.

        Prepends with session.email, and replaces spaces with dashes.

        TODO: follow rules in http://git-scm.com/docs/git-check-ref-format.html
    '''
    safe_description = description.replace('.', '-').replace(' ', '-')
    return quote(session['email'], '@.-_') + '/' + quote(safe_description, '-_!')

def branch_name2path(branch_name):
    ''' Quote the branch name for safe use in URLs.

        Uses urllib.quote() *twice* because Flask still interprets
        '%2F' in a path as '/', so it must be double-escaped to '%252F'.
    '''
    return quote(quote(branch_name, ''), '')

def branch_var2name(branch_path):
    ''' Unquote the branch name for use by Git.

        Uses urllib.unquote() *once* because Flask routing already converts
        raw paths to variables before they arrive here.
    '''
    return unquote(branch_path)

def path_type(file_path):
    '''
    '''
    if isdir(file_path):
        return 'folder'

    if str(guess_type(file_path)[0]).startswith('image/'):
        return 'image'

    return 'file'

def is_editable(file_path):
    '''
    '''
    try:
        if isdir(file_path):
            return False

        if open(file_path).read(4).startswith('---'):
            return True

    except:
        pass

    return False

def get_auth_data_file(data_href):
    ''' Get a file-like object for authentication CSV data.
    '''
    csv_url = get_auth_csv_url(data_href)
    
    url_base = 'file://{}'.format(realpath(__file__))
    real_url = urljoin(url_base, csv_url)
    
    if urlparse(real_url).scheme in ('file', ''):
        file_path = urlparse(real_url).path
        Logger.debug('Opening {} as auth CSV file'.format(file_path))
        return open(file_path, 'r')
    
    Logger.debug('Opening {} as auth CSV file'.format(real_url))
    return BytesIO(get(real_url).content)

def get_auth_csv_url(data_href):
    ''' Optionally convert link to GDocs spreadsheet to CSV format.
    '''
    _, host, path, _, _, _ = urlparse(data_href)
    
    gdocs_pat = re.compile(r'/spreadsheets/d/(?P<id>[\w\-]+)')
    path_match = gdocs_pat.match(path)
    
    if host == 'docs.google.com' and path_match:
        auth_path = '/spreadsheets/d/{}/export'.format(path_match.group('id'))
        return 'https://{host}{auth_path}?format=csv'.format(**locals())
    
    return data_href

def is_allowed_email(file, email):
    ''' Return true if given email address is allowed in given CSV file.
    
        First argument is a file-like object.
    '''
    domain_index, address_index = None, None
    domain_pat = re.compile(r'^(.*@)?(?P<domain>.+)$')
    email_domain = domain_pat.match(email).group('domain')
    rows = csv.reader(file)
    
    #
    # Look for a header row.
    #
    for row in rows:
        row = [val.lower() for val in row]
        starts_right = row[:2] == ['email domain', 'organization']
        ends_right = row[-3:] == ['email address', 'organization', 'name']
        if starts_right or ends_right:
            domain_index = 0 if starts_right else None
            address_index = -3 if ends_right else None
            break
    
    #
    # Look for possible matching data row.
    #
    for row in rows:
        if domain_index is not None:
            if domain_pat.match(row[domain_index]):
                domain = domain_pat.match(row[domain_index]).group('domain')
                if email_domain == domain:
                    return True

        if address_index is not None:
            if email == row[address_index]:
                return True
        
    return False

def login_required(route_function):
    ''' Login decorator for route functions.

        Adapts http://flask.pocoo.org/docs/patterns/viewdecorators/
    '''
    @wraps(route_function)
    def decorated_function(*args, **kwargs):
        email = session.get('email', None)

        if not email:
            return redirect('/not-allowed')
        
        auth_data_href = current_app.config['AUTH_DATA_HREF']
        if not is_allowed_email(get_auth_data_file(auth_data_href), email):
            return redirect('/not-allowed')

        environ['GIT_AUTHOR_NAME'] = ' '
        environ['GIT_AUTHOR_EMAIL'] = email
        environ['GIT_COMMITTER_NAME'] = ' '
        environ['GIT_COMMITTER_EMAIL'] = email

        return route_function(*args, **kwargs)

    return decorated_function

def _remote_exists(repo, remote):
    ''' Check whether a named remote exists in a repository.

        This should be as simple as `remote in repo.remotes`,
        but GitPython has a bug in git.util.IterableList:

            https://github.com/gitpython-developers/GitPython/issues/11
    '''
    try:
        repo.remotes[remote]

    except IndexError:
        return False

    else:
        return True

def synch_required(route_function):
    ''' Decorator for routes needing a repository synched to upstream.

        Syncs with upstream origin before and after. Use below @login_required.
    '''
    @wraps(route_function)
    def decorated_function(*args, **kwargs):
        Logger.debug('<' * 40 + '-' * 40)

        repo = Repo(current_app.config['REPO_PATH'])

        if _remote_exists(repo, 'origin'):
            Logger.debug('  fetching origin {}'.format(repo))
            repo.git.fetch('origin', with_exceptions=True)

        Logger.debug('- ' * 40)

        response = route_function(*args, **kwargs)

        # Push to origin only if the request method indicates a change.
        if request.method in ('PUT', 'POST', 'DELETE'):
            Logger.debug('- ' * 40)

            if _remote_exists(repo, 'origin'):
                Logger.debug('  pushing origin {}'.format(repo))
                repo.git.push('origin', all=True, with_exceptions=True)

        Logger.debug('-' * 40 + '>' * 40)

        return response

    return decorated_function

def synched_checkout_required(route_function):
    ''' Decorator for routes needing a repository checked out to a branch.

        Syncs with upstream origin before and after. Use below @login_required.
    '''
    @wraps(route_function)
    def decorated_function(*args, **kwargs):
        Logger.debug('<' * 40 + '-' * 40)

        repo = Repo(current_app.config['REPO_PATH'])

        if _remote_exists(repo, 'origin'):
            Logger.debug('  fetching origin {}'.format(repo))
            repo.git.fetch('origin', with_exceptions=True)

        checkout = get_repo(current_app)
        branch_name = branch_var2name(kwargs['branch'])
        master_name = current_app.config['default_branch']
        branch = start_branch(checkout, master_name, branch_name)
        branch.checkout()

        Logger.debug('  checked out to {}'.format(branch))
        Logger.debug('- ' * 40)

        response = route_function(*args, **kwargs)

        # Push to origin only if the request method indicates a change.
        if request.method in ('PUT', 'POST', 'DELETE'):
            Logger.debug('- ' * 40)

            if _remote_exists(repo, 'origin'):
                Logger.debug('  pushing origin {}'.format(repo))
                repo.git.push('origin', all=True, with_exceptions=True)

        Logger.debug('-' * 40 + '>' * 40)

        return response

    return decorated_function

def sorted_paths(repo, branch, path=None):
    full_path = join(repo.working_dir, path or '.').rstrip('/')
    all_sorted_files_dirs = sorted(listdir(full_path))

    filtered_sorted_files_dirs = [i for i in all_sorted_files_dirs if not i.startswith('.')]
    file_names = [n for n in filtered_sorted_files_dirs if not n.startswith('_')]
    view_paths = [join('/tree/%s/view' % branch_name2path(branch), join(path or '', fn))
                  for fn in file_names]

    full_paths = [join(full_path, name) for name in file_names]
    path_pairs = zip(full_paths, view_paths)

    list_paths = [(basename(fp), vp, path_type(fp), is_editable(fp))
                  for (fp, vp) in path_pairs if realpath(fp) != repo.git_dir]
    return list_paths

def directory_paths(branch, path=None):
    root_dir_with_path = [('root', '/tree/%s/edit' % branch_name2path(branch))]
    if path is None:
        return root_dir_with_path
    directory_list = [dir_name for dir_name in path.split('/')
                      if dir_name and not dir_name.startswith('.')]

    dirs_with_paths = [(dir_name, get_directory_path(branch, path, dir_name))
                       for dir_name in directory_list]
    return root_dir_with_path + dirs_with_paths

def get_directory_path(branch, path, dir_name):
    dir_index = path.find(dir_name + '/')
    current_path = path[:dir_index] + dir_name + '/'
    return join('/tree/%s/edit' % branch_name2path(branch), current_path)

def should_redirect():
    ''' Return True if the current flask.request should redirect.
    '''
    if request.args.get('go') == u'\U0001f44c':
        return False

    referer_url = request.headers.get('Referer')

    if not referer_url:
        return False

    return needs_redirect(request.host, request.path, referer_url)

def make_redirect():
    ''' Return a flask.redirect for the current flask.request.
    '''
    referer_url = request.headers.get('Referer')

    other = redirect(get_redirect(request.path, referer_url), 302)
    other.headers['Cache-Control'] = 'no-store private'
    other.headers['Vary'] = 'Referer'

    return other

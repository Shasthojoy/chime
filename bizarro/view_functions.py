from os.path import join, isdir, realpath
from os import environ
from urllib import quote, unquote
from mimetypes import guess_type
from functools import wraps

from git import Repo
from flask import request, session, current_app

from .repo_functions import start_branch

def dos2unix(string):
    ''' Returns a copy of the strings with line-endings corrected.
    '''
    return string.replace('\r\n', '\n').replace('\r', '\n')

def get_repo(flask_app):
    ''' Gets repository for the current user, cloned from the origin.
    '''
    dir_name = 'repo-' + session.get('email', 'nobody')
    user_dir = realpath(join(flask_app.config['WORK_PATH'], quote(dir_name)))
    
    if isdir(user_dir):
        user_repo = Repo(user_dir)
        user_repo.git.reset(hard=True)
        user_repo.remotes.origin.fetch()
        return user_repo
    
    source_repo = Repo(flask_app.config['REPO_PATH'])
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

def login_required(route_function):
    ''' Login decorator for route functions.
    
        Adapts http://flask.pocoo.org/docs/patterns/viewdecorators/
    '''
    @wraps(route_function)
    def decorated_function(*args, **kwargs):
        email = session.get('email', None)
    
        if not email:
            return redirect('/')
        
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
        print '<' * 40 + '-' * 40

        repo = Repo(current_app.config['REPO_PATH'])
    
        if _remote_exists(repo, 'origin'):
            print '  fetching origin', repo
            repo.git.fetch('origin', with_exceptions=True)

        print '- ' * 40

        response = route_function(*args, **kwargs)
        
        # Push to origin only if the request method indicates a change.
        if request.method in ('PUT', 'POST', 'DELETE'):
            print '- ' * 40

            if _remote_exists(repo, 'origin'):
                print '  pushing origin', repo
                repo.git.push('origin', with_exceptions=True)

        print '-' * 40 + '>' * 40

        return response
    
    return decorated_function

def synched_checkout_required(route_function):
    ''' Decorator for routes needing a repository checked out to a branch.
    
        Syncs with upstream origin before and after. Use below @login_required.
    '''
    @wraps(route_function)
    def decorated_function(*args, **kwargs):
        print '<' * 40 + '-' * 40

        repo = Repo(current_app.config['REPO_PATH'])
        
        if _remote_exists(repo, 'origin'):
            print '  fetching origin', repo
            repo.git.fetch('origin', with_exceptions=True)

        checkout = get_repo(current_app)
        branch_name = branch_var2name(kwargs['branch'])
        master_name = current_app.config['default_branch']
        branch = start_branch(checkout, master_name, branch_name)
        branch.checkout()

        print '  checked out to', branch
        print '- ' * 40

        response = route_function(*args, **kwargs)
        
        # Push to origin only if the request method indicates a change.
        if request.method in ('PUT', 'POST', 'DELETE'):
            print '- ' * 40

            if _remote_exists(repo, 'origin'):
                print '  pushing origin', repo
                repo.git.push('origin', with_exceptions=True)

        print '-' * 40 + '>' * 40

        return response
    
    return decorated_function

from os.path import join, isdir, exists, realpath, basename, split, splitext
from os import listdir, environ
from urllib import quote, unquote
from re import compile, MULTILINE
from mimetypes import guess_type
from functools import wraps
from glob import glob

from git import Repo
from requests import post
from flask import Flask, redirect, request, Response, render_template, session
from jekyll import load_jekyll_doc, build_jekyll_site

import bizarro

_default_branch = 'master'
_repo_path = 'sample-site'

app = Flask(__name__)
app.secret_key = 'boop'

def dos2unix(string):
    ''' Returns a copy of the strings with line-endings corrected.
    '''
    return string.replace('\r\n', '\n').replace('\r', '\n')

def get_repo():
    ''' Gets repository for the current user, cloned from the origin.
    '''
    user_dir = realpath(quote('repo-' + session.get('email', 'nobody')))
    
    if isdir(user_dir):
        user_repo = Repo(user_dir)
        user_repo.remotes.origin.fetch()
        return user_repo
    
    source_repo = Repo(_repo_path)
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

def login_required(function):
    ''' Login decorator for route functions.
    
        Adapts http://flask.pocoo.org/docs/patterns/viewdecorators/
    '''
    @wraps(function)
    def decorated_function(*args, **kwargs):
        email = session.get('email', None)
    
        if not email:
            return redirect('/')
        
        environ['GIT_AUTHOR_NAME'] = ' '
        environ['GIT_AUTHOR_EMAIL'] = email
        environ['GIT_COMMITTER_NAME'] = ' '
        environ['GIT_COMMITTER_EMAIL'] = email

        return function(*args, **kwargs)
    
    return decorated_function

@app.route('/')
def index():
    r = Repo(_repo_path) # bare repo
    branch_names = [b.name for b in r.branches if b.name != _default_branch]
    
    list_items = []
    
    for name in branch_names:
        path = branch_name2path(name)

        base = r.git.merge_base(_default_branch, name)
        behind_raw = r.git.log(base+'..'+_default_branch, format='%H %at %ae')
        ahead_raw = r.git.log(base+'..'+name, format='%H %at %ae')
        
        pattern = compile(r'^(\w+) (\d+) (.+)$', MULTILINE)
        # behind = [r.commit(sha) for (sha, t, e) in pattern.findall(behind_raw)]
        # ahead = [r.commit(sha) for (sha, t, e) in pattern.findall(ahead_raw)]
        behind = pattern.findall(behind_raw)
        ahead = pattern.findall(ahead_raw)
        
        list_items.append(dict(name=name, path=path, behind=behind, ahead=ahead))
    
    kwargs = dict(items=list_items, email=session.get('email', None))
    return render_template('index.html', **kwargs)

@app.route('/sign-in', methods=['POST'])
def sign_in():
    posted = post('https://verifier.login.persona.org/verify',
                  data=dict(assertion=request.form.get('assertion'),
                            audience='http://127.0.0.1:5000'))

    response = posted.json()
    
    if response.get('status', '') == 'okay':
        session['email'] = response['email']
        return 'OK'
    
    return Response('Failed', code=400)

@app.route('/sign-out', methods=['POST'])
def sign_out():
    if 'email' in session:
        session.pop('email')

    return 'OK'

@app.route('/start', methods=['POST'])
@login_required
def start_branch():
    r = get_repo()
    branch_desc = request.form.get('branch')
    branch_name = name_branch(branch_desc)
    branch = bizarro.repo.start_branch(r, _default_branch, branch_name)
    
    safe_branch = branch_name2path(branch.name)
    
    return redirect('/tree/%s/edit/' % safe_branch, code=303)

@app.route('/merge', methods=['POST'])
@login_required
def merge_branch():
    r = get_repo()
    branch_name = request.form.get('branch')
    branch = r.branches[branch_name]
    
    try:
        action = request.form.get('action', '').lower()
        args = r, _default_branch, branch_name
        
        if action == 'merge':
            bizarro.repo.complete_branch(*args)
        elif action == 'abandon':
            bizarro.repo.abandon_branch(*args)
        elif action == 'clobber':
            bizarro.repo.clobber_default_branch(*args)
        else:
            raise Exception('I do not know what "%s" means' % action)
    
    except bizarro.repo.MergeConflict as conflict:
    
        diffs = conflict.remote_commit.diff(conflict.local_commit)
        
        new_files = [d.b_blob.name for d in diffs if d.new_file]
        gone_files = [d.a_blob.name for d in diffs if d.deleted_file]
        changed_files = [d.a_blob.name for d in diffs if not (d.deleted_file or d.new_file)]
        
        kwargs = dict(branch=branch_name, new_files=new_files,
                      gone_files=gone_files, changed_files=changed_files)
        
        return render_template('merge-conflict.html', **kwargs)
    
    else:
        return redirect('/')

@app.route('/tree/<branch>/view/', methods=['GET'])
@app.route('/tree/<branch>/view/<path:path>', methods=['GET'])
@login_required
def branch_view(branch, path=None):
    branch = branch_var2name(branch)

    r = get_repo()
    b = bizarro.repo.start_branch(r, _default_branch, branch)
    b.checkout()
    c = r.commit()
    
    build_jekyll_site(r.working_dir)
    
    local_base, _ = splitext(join(join(r.working_dir, '_site'), path or ''))
    
    if isdir(local_base):
        local_base += '/index'
    
    local_paths = glob(local_base + '.*')
    
    if not local_paths:
        return 404
    
    local_path = local_paths[0]
    mime_type, _ = guess_type(local_path)
    
    return Response(open(local_path).read(), 200, {'Content-Type': mime_type})

@app.route('/tree/<branch>/edit/', methods=['GET'])
@app.route('/tree/<branch>/edit/<path:path>', methods=['GET'])
@login_required
def branch_edit(branch, path=None):
    branch = branch_var2name(branch)

    r = get_repo()
    b = bizarro.repo.start_branch(r, _default_branch, branch)
    b.checkout()
    c = r.commit()
    
    full_path = join(r.working_dir, path or '.').rstrip('/')
    safe_branch = branch_name2path(branch)
    
    if isdir(full_path):
        if path and not path.endswith('/'):
            return redirect('/tree/%s/edit/%s' % (safe_branch, path + '/'), code=302)
    
        file_names = [n for n in listdir(full_path) if not n.startswith('_')]
        view_paths = [join('/tree/%s/view' % branch_name2path(branch), join(path or '', fn))
                      for fn in file_names]
        
        full_paths = [join(full_path, name) for name in file_names]
        path_pairs = zip(full_paths, view_paths)
        
        list_paths = [(basename(fp), vp) for (fp, vp) in path_pairs if realpath(fp) != r.git_dir]
        kwargs = dict(branch=branch, email=session['email'], list_paths=list_paths)
        kwargs['needs_peer_review'] = bizarro.repo.needs_peer_review(r, _default_branch)
        kwargs['is_peer_reviewed'] = bizarro.repo.is_peer_reviewed(r, _default_branch)

        return render_template('tree-branch-edit-listdir.html', **kwargs)
    
    with open(full_path, 'r') as file:
        front, body = load_jekyll_doc(file)
        
        url_slug, _ = splitext(path)
        view_path = join('/tree/%s/view' % branch_name2path(branch), path)
        
        kwargs = dict(branch=branch, safe_branch=safe_branch,
                      body=body, hexsha=c.hexsha, url_slug=url_slug,
                      front=front, email=session['email'],
                      view_path=view_path, edit_path=path)

        return render_template('tree-branch-edit-file.html', **kwargs)

@app.route('/tree/<branch>/edit/', methods=['POST'])
@app.route('/tree/<branch>/edit/<path:path>', methods=['POST'])
@login_required
def branch_edit_file(branch, path=None):
    branch = branch_var2name(branch)

    r = get_repo()
    b = bizarro.repo.start_branch(r, _default_branch, branch)
    b.checkout()
    c = b.commit
    
    action = request.form.get('action', '').lower()
    do_save = True
    
    if action == 'upload' and 'file' in request.files:
        file_path = bizarro.edit.upload_new_file(r, path, request.files['file'])
        message = 'Uploaded new file "%s"' % file_path
        path_303 = path or ''
    
    elif action == 'add' and 'path' in request.form:
        front, body = dict(title='', layout='multi'), ''
        name = splitext(request.form['path'])[0] + '.md'

        file_path = bizarro.edit.create_new_page(r, path, name, front, body)
        message = 'Created new file "%s"' % file_path
        path_303 = file_path
    
    elif action == 'delete' and 'path' in request.form:
        file_path = bizarro.edit.delete_file(r, path, request.form['path'])
        message = 'Deleted file "%s"' % file_path
        path_303 = path or ''
    
    else:
        raise Exception()
    
    if do_save:
        bizarro.repo.save_working_file(r, file_path, message, c.hexsha, _default_branch)

    safe_branch = branch_name2path(branch)

    return redirect('/tree/%s/edit/%s' % (safe_branch, path_303), code=303)

@app.route('/tree/<branch>/save/<path:path>', methods=['POST'])
@login_required
def branch_save(branch, path):
    branch = branch_var2name(branch)

    r = get_repo()
    b = bizarro.repo.start_branch(r, _default_branch, branch)
    c = b.commit
    
    if c.hexsha != request.form.get('hexsha'):
        raise Exception('Out of date SHA: %s' % request.form.get('hexsha'))
    
    #
    # Write changes.
    #
    b.checkout()
    
    front = {'layout': dos2unix(request.form.get('layout')),
             'title':  dos2unix(request.form.get('title')),
             'title-es': dos2unix(request.form.get('title-es')),
             'body-es':  dos2unix(request.form.get('body-es')),
             'title-zh-cn': dos2unix(request.form.get('title-zh-cn')),
             'body-zh-cn':  dos2unix(request.form.get('body-zh-cn'))}

    body = dos2unix(request.form.get('body'))
    bizarro.edit.update_page(r, path, front, body)
    
    #
    # Try to merge from the master to the current branch.
    #
    try:
        message = 'Saved file "%s"' % path
        c2 = bizarro.repo.save_working_file(r, path, message, c.hexsha, _default_branch)
        new_path = request.form.get('url-slug') + splitext(path)[1]
        
        if new_path != path:
            bizarro.repo.move_existing_file(r, path, new_path, c2.hexsha, _default_branch)
            path = new_path
    
    except bizarro.repo.MergeConflict as conflict:
        r.git.reset(c.hexsha, hard=True)
    
        print 1, conflict.remote_commit
        print ' ', repr(conflict.remote_commit.tree[path].data_stream.read())
        print 2, conflict.local_commit
        print ' ', repr(conflict.local_commit.tree[path].data_stream.read())
        raise
    
    safe_branch = branch_name2path(branch)

    return redirect('/tree/%s/edit/%s' % (safe_branch, path), code=303)

if __name__ == '__main__':
    app.run(debug=True)
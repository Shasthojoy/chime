from logging import getLogger
logger = getLogger('bizarro.publish.functions')

from urlparse import urlparse
from zipfile import ZipFile, ZIP_DEFLATED
from os.path import dirname, basename, join, exists, relpath
from tempfile import mkdtemp
from shutil import rmtree
from io import BytesIO
from os import walk

from requests import get

from ..jekyll_functions import build_jekyll_site

def process_commit(commit_url, commit_sha):
    '''
    '''
    try:
        working_dir = mkdtemp()
        checkout_dir = extract_github_commit(working_dir, commit_url, commit_sha)
        built_dir = build_jekyll_site(checkout_dir)
        content = archive_commit(built_dir)
        
    except Exception as e:
        print e
        logger.warning(e)

    finally:
        rmtree(working_dir)

def extract_github_commit(work_dir, commit_url, commit_sha):
    ''' Extract a single commit from Github to a directory and return its path.
    '''
    #
    # Convert commit URL to downloadable archive URL.
    # Old: https://github.com/codeforamerica/ceviche-starter/commit/93250f1308daef66c5809fe87fc242d092e61db7
    # New: https://github.com/codeforamerica/ceviche-starter/archive/93250f1308daef66c5809fe87fc242d092e61db7.zip
    #
    _, _, path, _, _, _ = urlparse(commit_url)
    parts = dict(repo=dirname(dirname(path)), sha=commit_sha)
    tarball_url = 'https://github.com{repo}/archive/{sha}.zip'.format(**parts)
    
    got = get(tarball_url)
    zip = ZipFile(BytesIO(got.content), 'r')
    zip.extractall(work_dir)
    
    #
    # Check for a specially-named subdirectory made by Github.
    # ceviche-starter-93250f1308daef66c5809fe87fc242d092e61db7
    #
    subdirectory = '{}-{}'.format(basename(parts['repo']), commit_sha)
    checkout_dir = join(work_dir, subdirectory)
    
    if not exists(checkout_dir):
        checkout_dir = work_dir
    
    return checkout_dir

def archive_commit(directory):
    ''' Pack directory into a zip archive, return BytesIO buffer.
    '''
    content = BytesIO()
    zip = ZipFile(content, 'w', ZIP_DEFLATED)
    
    for (dirpath, _, filenames) in walk(directory):
        for filename in filenames:
            filepath = join(dirpath, filename)
            archpath = relpath(filepath, directory)
            zip.write(filepath, archpath)
    
    zip.printdir()
    print len(content.getvalue()), 'bytes'
    
    return content

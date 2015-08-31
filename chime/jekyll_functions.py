'''
Dump and load complete Jekyll files.

Provides two functions, load_jekyll_doc() and dump_jekyll_doc(), that read and
write YAML-formatted front matter and arbitrary bytes after a "---" separator.

Test with short sample data:

    >>> from StringIO import StringIO
    >>> front, body, file = dict(title=u'Greeting'), 'World: hello.', StringIO()
    >>> dump_jekyll_doc(front, body, file)
    >>> _front, _body = load_jekyll_doc(file)

Input and output are identical:

    >>> _front['title'] == front['title'] and _body == body
    True

Jekyll likes to have the "---" document separator at the top:

    >>> file.seek(0)
    >>> file.read(4) == _marker
    True
'''
from __future__ import absolute_import

from os.path import join, exists
from collections import OrderedDict
import yaml
import logging
from . import constants

_marker = "---\n"

def load_languages(directory):
    ''' Load languages from site configuration.

        Configuration language block will look like this:

            languages:
            - iso: name
            - iso: name

        The dashes tell YAML that it's ordered.
    '''
    config_path = join(directory, '_config.yml')

    if exists(config_path):
        with open(config_path) as file:
            config = yaml.load(file).get('languages', [])

        if type(config) is not list:
            raise ValueError(u'Unable to load language options.')
    else:
        config = []

    languages = OrderedDict()

    for iso_name in config:
        for (iso, name) in iso_name.items():
            languages[iso] = name

    # We want English always present.
    if constants.ISO_CODE_ENGLISH not in languages:
        languages[constants.ISO_CODE_ENGLISH] = constants.ISO_NAME_ENGLISH

    return languages

def load_yaml_and_body(file):
    for token in yaml.scan(file):
        # Look for a token that shows we're about to reach the content.
        if type(token) is yaml.DocumentStartToken:

            # Seek to the beginning, and load the complete content.
            file.seek(0)
            chars = file.read().decode('utf-8')

            # Load the front matter as a document.
            front_matter = yaml.safe_load(chars[:token.end_mark.index])

            # Seek just after the document separator, and get remaining string.
            content = chars[token.end_mark.index + len("\n" + _marker):]

            return front_matter, content

    raise Exception('Couldn\'t find yaml.DocumentStartToken when loading a file.')

def load_jekyll_doc(file):
    ''' Load jekyll front matter and remaining content from a file.

        Sample output:

          {"title": "Greetings"}, "Hello world."
    '''
    # Check for presence of document separator.
    file.seek(0)

    if file.read(len(_marker)) == _marker:
        file.seek(len(_marker))
        return load_yaml_and_body(file)
    else:
        file.seek(0)
        return {}, file.read().decode('utf-8')

def dump_jekyll_doc(front_matter, content, file):
    ''' Dump jekyll front matter and content to a file.

        To provide some guarantee of human-editable output, front matter
        is dumped using the newline-preserving block literal form.

        Sample output:

          ---
          "title": |-
            Greetings
          ---
          Hello world.
    '''
    # Use newline-preserving block literal form.
    # yaml.SafeDumper ensures best unicode output.
    dump_kwargs = dict(Dumper=yaml.SafeDumper, default_flow_style=False,
                       canonical=False, default_style='|', indent=2,
                       allow_unicode=True)

    # Write front matter to the start of the file.
    file.seek(0)
    file.truncate()
    file.write(_marker)
    yaml.dump(front_matter, file, **dump_kwargs)

    # Write content to the end of the file.
    content = content or u''
    file.write(_marker)
    file.write(content.encode('utf-8'))

def build_jekyll_site(dirname):
    ''' Build the Jekyll site inside dirname, return path to the built site.
    '''

    from subprocess import Popen
    import os

    python_dir = os.path.dirname(os.path.realpath(__file__))
    project_dir = os.path.join(python_dir, "..")
    jekyll_script = os.path.realpath(os.path.join(project_dir, 'jekyll/run-jekyll.sh'))

    call = [jekyll_script, 'build']
    try:
        build = Popen(call, cwd=dirname)
        build.wait()
    except:
        error_message = u'Unexpected Jekyll failure running {} in {}'.format(call, dirname)
        logger = logging.getLogger('chime.jekyll')
        logger.error(error_message)
        raise Exception(error_message)

    # By default Jekyll builds into dirname/_site
    return join(dirname, '_site')

if __name__ == '__main__':
    import doctest
    doctest.testmod()

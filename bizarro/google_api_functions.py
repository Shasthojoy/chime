from flask import current_app, redirect, session
from requests import post, get
from urllib import urlencode
import random
from string import ascii_uppercase, digits
import os
import posixpath
import json
from datetime import date, timedelta
from .view_functions import WriteLocked, ReadLocked

GA_CONFIG_FILENAME = 'ga_config.json'
GOOGLE_ACCESS_TOKEN_URL = 'https://accounts.google.com/o/oauth2/token'
GOOGLE_PLUS_WHOAMI_URL = 'https://www.googleapis.com/plus/v1/people/me'
GOOGLE_ANALYTICS_PROPERTIES_URL = 'https://www.googleapis.com/analytics/v3/management/accounts/~all/webproperties'

def authorize_google():
    ''' Authorize google via oauth2
    '''
    #
    # This is how google says the state should be generated
    #
    state = ''.join(random.choice(ascii_uppercase + digits) for x in xrange(32))
    session['state'] = state

    query_string = urlencode(dict(client_id=current_app.config['GA_CLIENT_ID'], redirect_uri=current_app.config['GA_REDIRECT_URI'], scope='openid profile https://www.googleapis.com/auth/analytics', state=state, response_type='code', access_type='offline', approval_prompt='force'))
    return redirect('https://accounts.google.com/o/oauth2/auth' + '?' + query_string)

def get_google_client_info():
    ''' Return client ID and secret for Google OAuth use.
    '''
    return current_app.config['GA_CLIENT_ID'], current_app.config['GA_CLIENT_SECRET']

def request_new_google_access_and_refresh_tokens(request):
    ''' Get new access and refresh tokens from the Google API.
    '''
    if request.args.get('state') != session['state']:
        raise Exception()

    code = request.args.get('code')
    redirect_uri = '{0}://{1}/callback'.format(request.scheme, request.host)

    data = dict(client_id=current_app.config['GA_CLIENT_ID'], client_secret=current_app.config['GA_CLIENT_SECRET'],
                code=code, redirect_uri=redirect_uri,
                grant_type='authorization_code')

    response = post(GOOGLE_ACCESS_TOKEN_URL, data=data)
    access = response.json()

    if response.status_code != 200:
        if 'error_description' in access:
            raise Exception('Google says "{0}"'.format(access['error_description']))
        else:
            raise Exception('Google Error')

    # write the new tokens to the config file
    ga_config_path = os.path.join(current_app.config['RUNNING_STATE_DIR'], GA_CONFIG_FILENAME)
    with WriteLocked(ga_config_path) as iofile:
        # read the json from the file
        ga_config = json.load(iofile)
        # change the values of the access and refresh tokens
        ga_config['access_token'] = access['access_token']
        ga_config['refresh_token'] = access['refresh_token']
        # write the new config json
        iofile.seek(0)
        iofile.truncate(0)
        json.dump(ga_config, iofile, indent=2, ensure_ascii=False)

    return access['access_token'], access['refresh_token']

def get_google_personal_info(access_token):
    ''' Get account name and email from Google Plus.
    '''
    response = get(GOOGLE_PLUS_WHOAMI_URL, params={'access_token': access_token})
    whoami = response.json()

    if response.status_code != 200:
        if 'error_description' in whoami:
            raise Exception('Google says "{0}"'.format(whoami['error_description']))
        else:
            raise Exception('Google Error')

    emails = dict([(e['type'], e['value']) for e in whoami['emails']])
    email = emails.get('account', whoami['emails'][0]['value'])
    name = whoami['displayName']

    return name, email

def get_google_analytics_properties(access_token):
    ''' Get sorted list of web properties from Google Analytics.
    '''
    response = get(GOOGLE_ANALYTICS_PROPERTIES_URL, params={'access_token': access_token})
    items = response.json()

    if response.status_code != 200:
        if 'error_description' in items:
            raise Exception('Google says "{0}"'.format(items['error_description']))
        else:
            raise Exception('Google Error')

    properties = [
        (item['defaultProfileId'], item['name'], item['websiteUrl'])
        for item in items['items']
        if item.get('defaultProfileId', False)
    ]

    properties.sort(key=lambda p: p[1].lower())

    return properties

def get_new_access_token(refresh_token):
    ''' Get a new access token with the refresh token so a user doesn't need to
        authorize the app again
    '''
    if not refresh_token:
        return False

    data = dict(client_id=current_app.config['GA_CLIENT_ID'], client_secret=current_app.config['GA_CLIENT_SECRET'],
                refresh_token=refresh_token, grant_type='refresh_token')

    resp = post(GOOGLE_ACCESS_TOKEN_URL, data=data)

    if resp.status_code != 200:
        raise Exception()

    access = json.loads(resp.content)

    # write the new token to the config file
    ga_config_path = os.path.join(current_app.config['RUNNING_STATE_DIR'], GA_CONFIG_FILENAME)
    with WriteLocked(ga_config_path) as iofile:
        # read the json from the file
        ga_config = json.load(iofile)
        # change the value of the access token
        ga_config['access_token'] = access['access_token']
        # write the new config json
        iofile.seek(0)
        iofile.truncate(0)
        json.dump(ga_config, iofile, indent=2, ensure_ascii=False)

    return True

def get_ga_page_path_pattern(page_path, project_domain):
    ''' Get a regex pattern that'll get us the google analytics data we want.
        Builds a pattern that looks like: codeforamerica.org/about/(index.html|index|)
    '''
    page_path_dir, page_path_filename = posixpath.split(page_path)
    filename_base, filename_ext = posixpath.splitext(page_path_filename)
    # if the filename is 'index', allow no filename as an option
    or_else = '|' if (filename_base == 'index') else ''
    filename_pattern = '({page_path_filename}|{filename_base}{or_else})'.format(**locals())
    # make sure that no None values are passed to the join method
    project_domain = project_domain or u''
    page_path_dir = page_path_dir or u''
    filename_pattern = filename_pattern or u''
    return posixpath.join(project_domain, page_path_dir, filename_pattern)

def fetch_google_analytics_for_page(config, page_path, access_token):
    ''' Get stats for a particular page
    '''
    ga_config_path = os.path.join(config['RUNNING_STATE_DIR'], GA_CONFIG_FILENAME)
    with ReadLocked(ga_config_path) as infile:
        ga_config = json.load(infile)
    ga_project_domain = ga_config['project_domain']
    ga_profile_id = ga_config['profile_id']

    start_date = (date.today() - timedelta(days=7)).isoformat()
    end_date = date.today().isoformat()

    page_path_pattern = get_ga_page_path_pattern(page_path, ga_project_domain)

    query_string = urlencode({'ids': 'ga:' + ga_profile_id, 'dimensions': 'ga:previousPagePath,ga:pagePath',
                              'metrics': 'ga:pageViews,ga:avgTimeOnPage,ga:exitRate',
                              'filters': 'ga:pagePath=~' + page_path_pattern, 'start-date': start_date,
                              'end-date': end_date, 'max-results': '1', 'access_token': access_token})

    resp = get('https://www.googleapis.com/analytics/v3/data/ga' + '?' + query_string)
    response_list = resp.json()

    if u'error' in response_list:
        return {}
    else:
        average_time = unicode(int(float(response_list['totalsForAllResults']['ga:avgTimeOnPage'])))
        analytics_dict = {'page_views': response_list['totalsForAllResults']['ga:pageViews'],
                          'average_time_page': average_time,
                          'start_date': start_date, 'end_date': end_date}
        return analytics_dict

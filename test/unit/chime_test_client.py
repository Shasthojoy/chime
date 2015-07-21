# -- coding: utf-8 --
from __future__ import absolute_import

from bs4 import BeautifulSoup
from urlparse import urlparse, urljoin
from re import search
from chime import repo_functions

class ChimeTestClient:
    ''' Stateful client for Chime Flask test client.
    '''
    def __init__(self, client, test):
        ''' Create a new client, with Flask test client and TestCase instances.
        '''
        self.client = client
        self.test = test

        response = self.client.get('/')
        self.test.assertFalse('Start' in response.data)

        self.path, self.soup = '/', BeautifulSoup(response.data)

    def sign_in(self, email):
        ''' Sign in with a given email address.

            Should be used inside an HTTMock that overrides Chime's internal
            call to Persona verifier: https://verifier.login.persona.org/verify
        '''
        response = self.client.post('/sign-in', data={'email': email})
        self.test.assertEqual(response.status_code, 200)

        response = self.client.get('/')
        self.test.assertTrue('Start' in response.data)

    def reload(self):
        ''' Reload the current path.
        '''
        self.open_link(self.path)

    def open_link(self, url):
        ''' Open a link
        '''
        response = self.client.get(url)
        self.test.assertEqual(response.status_code, 200)

        self.path, self.soup = url, BeautifulSoup(response.data)

    def open_link_blindly(self, url):
        ''' Open a link without testing
        '''
        response = self.client.get(url)

        self.path, self.soup = url, BeautifulSoup(response.data)

    def follow_link(self, href):
        ''' Follow a link after making sure it's present in the page.
        '''
        # Look for the link
        link = self.soup.find(lambda tag: bool(tag.name == 'a' and tag['href'] == href))
        response = self.client.get(link['href'])
        self.test.assertTrue(response.status_code in (301, 302)) # Watch out for a redirect here.

        # Load the page
        redirect = urlparse(response.headers['Location']).path
        response = self.client.get(redirect)
        self.test.assertEqual(response.status_code, 200)

        self.path, self.soup = redirect, BeautifulSoup(response.data)

    def follow_redirect(self, response, code):
        ''' Expect and follow a response HTTP redirect.
        '''
        self.test.assertEqual(response.status_code, code, 'Status {} should have been {}'.format(response.status_code, code))

        redirect = urlparse(response.headers['Location']).path
        response = self.client.get(redirect)
        self.test.assertEqual(response.status_code, 200)

        self.path, self.soup = redirect, BeautifulSoup(response.data)

    def get_branch_name(self):
        ''' Extract and return the branch name from the current soup.
        '''
        # Assumes there is an HTML comment in the format '<!-- branch: 1234567 -->'
        branch_search = search(r'<!-- branch: (.{{{}}}) -->'.format(repo_functions.BRANCH_NAME_LENGTH), unicode(self.soup))
        self.test.assertIsNotNone(branch_search)
        try:
            branch_name = branch_search.group(1)
        except AttributeError:
            raise Exception('No match for generated branch name.')

        return branch_name

    def start_task(self, description, beneficiary):
        ''' Start a new task.
        '''
        data = {'task_description': description, 'task_beneficiary': beneficiary}
        response = self.client.post('/start', data=data)

        if response.status_code == 200:
            self.soup = BeautifulSoup(response.data)
        else:
            self.follow_redirect(response, 303)

    def add_category(self, category_name):
        ''' Look for form to add a category, submit it.
        '''
        input = self.soup.find(lambda tag: bool(tag.name == 'input' and tag.get('placeholder') == 'Add Category'))
        form = input.find_parent('form')
        self.test.assertEqual(form['method'].upper(), 'POST')

        data = {i['name']: i.get('value', u'') for i in form.find_all('input')}
        data[input['name']] = category_name

        add_category_path = urlparse(urljoin(self.path, form['action'])).path
        response = self.client.post(add_category_path, data=data)

        # Drop down to where the subcategories are.
        self.follow_redirect(response, 303)

    def add_subcategory(self, subcategory_name):
        ''' Look for form to add a subcategory, submit it..
        '''
        input = self.soup.find(lambda tag: bool(tag.name == 'input' and tag.get('placeholder') == 'Add Subcategory'))
        form = input.find_parent('form')
        self.test.assertEqual(form['method'].upper(), 'POST')

        data = {i['name']: i.get('value', u'') for i in form.find_all('input')}
        data[input['name']] = subcategory_name

        add_subcategory_path = urlparse(urljoin(self.path, form['action'])).path
        response = self.client.post(add_subcategory_path, data=data)

        # Drop down into the subcategory where the articles are.
        self.follow_redirect(response, 303)

    def add_article(self, article_name):
        ''' Look for form to add an article, submit it.
        '''
        # Create a new article.

        input = self.soup.find(lambda tag: bool(tag.name == 'input' and tag.get('placeholder') == 'Add Article'))
        form = input.find_parent('form')
        self.test.assertEqual(form['method'].upper(), 'POST')

        data = {i['name']: i.get('value', u'') for i in form.find_all('input')}
        data[input['name']] = article_name

        add_article_path = urlparse(urljoin(self.path, form['action'])).path
        response = self.client.post(add_article_path, data=data)

        # View the new article.
        self.follow_redirect(response, 303)

    def edit_article(self, title_str, body_str):
        ''' Look for form to edit an article, submit it.
        '''
        body = self.soup.find(lambda tag: bool(tag.name == 'textarea' and tag.get('name') == 'en-body'))
        form = body.find_parent('form')
        title = form.find(lambda tag: bool(tag.name == 'input' and tag.get('name') == 'en-title'))
        self.test.assertEqual(form['method'].upper(), 'POST')

        data = {i['name']: i.get('value', u'')
                for i in form.find_all(['input', 'button', 'textarea'])
                if i.get('type') != 'submit'}

        data[title['name']] = title_str
        data[body['name']] = body_str

        edit_article_path = urlparse(urljoin(self.path, form['action'])).path
        response = self.client.post(edit_article_path, data=data)

        # View the updated article.
        self.follow_redirect(response, 303)

    def edit_outdated_article(self, title_str, body_str):
        ''' Look for form to edit an article we know to be outdated, submit it and assert that the sumbission fails.
        '''
        body = self.soup.find(lambda tag: bool(tag.name == 'textarea' and tag.get('name') == 'en-body'))
        form = body.find_parent('form')
        title = form.find(lambda tag: bool(tag.name == 'input' and tag.get('name') == 'en-title'))
        self.test.assertEqual(form['method'].upper(), 'POST')

        data = {i['name']: i.get('value', u'')
                for i in form.find_all(['input', 'button', 'textarea'])
                if i.get('type') != 'submit'}

        data[title['name']] = title_str
        data[body['name']] = body_str

        edit_article_path = urlparse(urljoin(self.path, form['action'])).path
        response = self.client.post(edit_article_path, data=data)
        self.test.assertEqual(response.status_code, 500)

    def follow_modify_category_link(self, title_str):
        ''' Find the (sub-)category edit button in the last soup and follow it.
        '''
        mod_link = self.soup.find(lambda tag: bool(tag.name == 'a' and tag.text == title_str))
        mod_li = mod_link.find_parent('li')
        mod_span = mod_li.find(lambda tag: bool(tag.name == 'span' and 'fa-pencil' in tag.get('class')))
        mod_link = mod_span.find_parent('a')
        self.follow_link(mod_link['href'])

    def delete_category(self):
        ''' Look for the delete button, submit it.
        '''
        body = self.soup.find(lambda tag: bool(tag.name == 'textarea' and tag.get('name') == 'en-description'))
        form = body.find_parent('form')
        self.test.assertEqual(form['method'].upper(), 'POST')

        data = {i['name']: i.get('value', u'')
                for i in form.find_all(['input', 'button', 'textarea'])
                if i.get('name') != 'save'}

        delete_category_path = urlparse(urljoin(self.path, form['action'])).path
        response = self.client.post(delete_category_path, data=data)

        self.follow_redirect(response, 303)

    def delete_article(self, title_str):
        ''' Look for the article delete button, submit it
        '''
        del_link = self.soup.find(lambda tag: bool(tag.name == 'a' and tag.text == title_str))
        del_li = del_link.find_parent('li')
        del_span = del_li.find(lambda tag: bool(tag.name == 'span' and 'fa-trash' in tag.get('class')))
        del_form = del_span.find_parent('form')

        self.test.assertEqual(del_form['method'].upper(), 'POST')

        data = {i['name']: i.get('value', u'')
                for i in del_form.find_all(['input', 'button', 'textarea'])}

        delete_article_path = urlparse(urljoin(self.path, del_form['action'])).path
        response = self.client.post(delete_article_path, data=data)

        self.follow_redirect(response, 303)

    def request_feedback(self, feedback_str):
        ''' Look for form to request feedback, submit it.
        '''
        body = self.soup.find(lambda tag: bool(tag.name == 'textarea' and tag.get('name') == 'comment_text'))
        form = body.find_parent('form')
        self.test.assertEqual(form['method'].upper(), 'POST')

        data = {i['name']: i.get('value', u'')
                for i in form.find_all(['input', 'button', 'textarea'])
                if i.get('value') != 'Leave a Comment'}

        data[body['name']] = feedback_str

        save_feedback_path = urlparse(urljoin(self.path, form['action'])).path
        response = self.client.post(save_feedback_path, data=data)

        # View the saved feedback.
        self.follow_redirect(response, 303)

    def leave_feedback(self, feedback_str):
        ''' Look for form to leave feedback, submit it.
        '''
        body = self.soup.find(lambda tag: bool(tag.name == 'textarea' and tag.get('name') == 'comment_text'))
        form = body.find_parent('form')
        self.test.assertEqual(form['method'].upper(), 'POST')

        data = {i['name']: i.get('value', u'')
                for i in form.find_all(['input', 'button', 'textarea'])
                if i.get('value') != 'Looks Good!'}

        data[body['name']] = feedback_str

        save_feedback_path = urlparse(urljoin(self.path, form['action'])).path
        response = self.client.post(save_feedback_path, data=data)

        # View the saved feedback.
        self.follow_redirect(response, 303)

    def approve_activity(self):
        ''' Look for form to approve activity, submit it.
        '''
        body = self.soup.find(lambda tag: bool(tag.name == 'textarea' and tag.get('name') == 'comment_text'))
        form = body.find_parent('form')
        self.test.assertEqual(form['method'].upper(), 'POST')

        data = {i['name']: i.get('value', u'')
                for i in form.find_all(['input', 'button', 'textarea'])
                if i.get('value') != 'Leave a Comment'}

        approve_activity_path = urlparse(urljoin(self.path, form['action'])).path
        response = self.client.post(approve_activity_path, data=data)

        # View the saved feedback.
        self.follow_redirect(response, 303)

    def publish_activity(self):
        ''' Look for form to publish activity, submit it.
        '''
        body = self.soup.find(lambda tag: bool(tag.name == 'textarea' and tag.get('name') == 'comment_text'))
        form = body.find_parent('form')
        self.test.assertEqual(form['method'].upper(), 'POST')

        data = {i['name']: i.get('value', u'')
                for i in form.find_all(['input', 'button', 'textarea'])
                if i.get('value') != 'Leave a Comment'}

        publish_activity_path = urlparse(urljoin(self.path, form['action'])).path
        response = self.client.post(publish_activity_path, data=data)

        # View the published activity.
        self.follow_redirect(response, 303)

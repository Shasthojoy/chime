# -- coding: utf-8 --

import os
from random import randint
from unittest import main
import sys
import time
import urllib

from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from acceptance.browser import Browser

from acceptance.chime_test_case import ChimeTestCase


BROWSERS_TO_TRY = Browser.from_string(os.environ.get('BROWSERS_TO_TEST'))
TEST_REPETITIONS = int(os.environ.get('TEST_REPETITIONS',"1"))


class TestPreview(ChimeTestCase):
    _multiprocess_can_split_ = True
    def setUp(self):
        self.email = self.mutate_email(os.environ['TESTING_EMAIL'])
        self.password = os.environ['TESTING_PASSWORD']
        self.host = self.load_hosts_file()[0]
        self.live_site = 'http://' + self.host

    def mutate_email(self, email):
        return email.replace('@', '+' + self.random_digits() + '@')

    def use_driver(self, browser=None):
        """
        :param capabilities: If particular browser are requested; it is passed along to BrowserStack.
            Otherwise, a local Firefox is used.
        """
        if browser:
            sys.stderr.write("Setting up for browser %s\n" % browser)
            mode = 'browserstack'
            if mode=='browserstack':
                capabilities = browser.as_browserstack_capabilities({'browserstack.debug': True, 'project': 'chime'})

                if browser.browser == 'IE':
                    capabilities['ignoreProtectedModeSettings'] = True
                self.driver = webdriver.Remote(
                    command_executor='http://chimetests1:AxRS34k3vrf7mu9zZ2hE@hub.browserstack.com:80/wd/hub',
                    desired_capabilities=capabilities)
            elif mode=='saucelabs':
                self.driver = webdriver.Remote(
                    command_executor="http://wpietri:42e45709-70f3-4eb8-9ebd-c85be6dfec7a@ondemand.saucelabs.com:80/wd/hub",
                    desired_capabilities=browser.as_saucelabs_capabilities())
            else:
                raise ValueError

        else:
            self.driver = webdriver.Chrome(executable_path='/usr/lib/chromium-browser/chromedriver')
            sys.stderr.write("Set up for Chrome\n")
        self.waiter = WebDriverWait(self.driver, timeout=60)
        self.driver.implicitly_wait(15) # seconds

    def load_hosts_file(self):
        with open(os.path.dirname(__file__) + '/../../fabfile/hosts.txt', 'rU') as f:
            hosts = f.read().split(',')
        if len(hosts) == 0:
            raise Exception('Please insert a test host')
        return hosts

    def switch_to_other_window(self, in_handle):
        ''' Switch to the first window found with a handle that's not in_handle
        '''

        def predicate(driver):

            for check_handle in driver.window_handles:
                if check_handle != in_handle:
                    driver.switch_to_window(check_handle)
                    return True

            return False

        return predicate



    def test_create_page_and_preview(self, browser=None):
        self.use_driver(browser)

        signin_method = "stubby_js"
        if signin_method=='magic_url':
            signin_link = self.live_site + '/sign-in?assertion={}\n'.format(urllib.quote_plus(self.email))
            sys.stderr.write("connecting to {}".format(signin_link))
            self.driver.get(signin_link)
            time.sleep(1)
        elif signin_method=='stubby_js':
           self.driver.get(self.live_site)
           self.driver.execute_script('window.navigator.id.stubby.setPersonaState("{}")'.format(self.email))
        elif signin_method=='stubby_ui':
            self.driver.get(self.live_site)
            main_window = self.driver.current_window_handle
            self.driver.find_element_by_id('signin').click()
            alert = self.driver.switch_to.alert
            alert.send_keys(self.email)
            alert.accept()
            self.driver.switch_to.window(main_window)
        else:
            raise ValueError

        self.driver.get(self.live_site) # this line works around an IE8 issue where quirks mode is sometimes triggered

        # make sure we have logged in
        # self.assertEqual("Current Activities", self.driver.find_element_by_css_selector('h2.current-tasks__title').text)

        main_url = self.driver.current_url

        sys.stderr.write("at url {}\n".format(main_url))

        # start a new task
        task_description = self.marked_string('task_description')
        self.driver.find_element_by_name('task_description').send_keys(task_description)
        self.driver.find_element_by_name('task_beneficiary').send_keys(self.marked_string('task_beneficiary'))
        main_window = self.driver.current_window_handle
        self.driver.find_element_by_class_name('create').click()

        # create a new page
        self.driver.find_element_by_xpath("//form[@action='.']/input[@name='path']").send_keys(self.marked_string('filename'))
        self.driver.find_element_by_xpath("//form[@action='.']/input[@type='submit']").click()


        # add some content to that page
        self.driver.find_element_by_name('en-title').send_keys(self.marked_string('title'))
        test_page_content = 'This is some test content.', Keys.RETURN, Keys.RETURN, self.marked_string('body_text'),\
                            Keys.RETURN, Keys.RETURN, '# This is a test h1', Keys.RETURN, Keys.RETURN, '> This is a test pull-quote'
        self.driver.find_element_by_id('en-body markItUp').send_keys(*test_page_content)

        # save the page
        self.driver.find_element_by_xpath("//input[@value='Save']").click()

        # preview the page
        self.driver.find_element(By.XPATH, "//a[@target='_blank']").click()

        # wait until the preview window's available and switch to it
        self.waiter.until(self.switch_to_other_window(main_window))
        self.waiter.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        self.driver.close()
        self.driver.switch_to.window(main_window)
        # TODO: make sure there's something there

        # go back to the main page
        self.driver.get(main_url)
        # delete our branch
        delete_button = self.driver.find_element_by_xpath(
            "//a[contains(text(),'{}')]/../..//button[@value='abandon']".format(task_description))
        self.scrollTo(delete_button)
        delete_button.click()
        # TODO: make sure deletion happens

    def random_digits(self, count=6):
        format_as = "{:0" + str(count) + "d}"
        return format_as.format(randint(0, 10 ** count - 1))

    def marked_string(self, base='string'):
        return "{}-{}".format(base, self.random_digits())


    def log_in_to_persona(self, main_window):
        self.driver.find_element_by_id('signin').click()
        # wait until the persona window's available and switch to it
        self.waiter.until(self.switch_to_other_window(main_window))
        self.waiter.until(EC.visibility_of_element_located((By.ID, 'authentication_email'))).send_keys(self.email)
        # there are many possible submit buttons on this page
        # so grab the whole row and then click the first button
        submit_row = self.driver.find_element_by_css_selector('.submit.cf.buttonrow')
        submit_row.find_element_by_css_selector('.isStart.isAddressInfo').click()
        # ajax, wait until the element is visible
        self.waiter.until(EC.visibility_of_element_located((By.ID, 'authentication_password'))).send_keys(self.password)
        submit_row.find_element_by_css_selector('.isReturning.isTransitionToSecondary').click()
        # switch back to the main window
        self.driver.switch_to.window(main_window)

    def onFailure(self, exception_info):
        super(TestPreview, self).onFailure(exception_info)
        self.screenshot()

    def screenshot(self):
        if self.driver:
            self.driver.save_screenshot("at-{}.png".format(time.strftime('%Y%m%d-%H%M%S', time.localtime())))
        else:
            sys.stderr.write("no driver to take screenshot\n")

    def onError(self, exception_info):
        super(TestPreview, self).onError(exception_info)
        self.screenshot()

    def tearDown(self):
        if self.driver:
            self.driver.quit()
        pass

    def scrollTo(self, element):
        ActionChains(self.driver).move_to_element(element).perform()
        element.send_keys(Keys.PAGE_DOWN)


def rewrite_for_all_browsers(browser_list, times=1):
    """
        Magically make test methods for all desired browsers. Note that this method cannot contain
        the word 'test' or nose will decide it is worth running.
    """
    # TODO: find test methods and rewrite them all
    name = 'test_create_page_and_preview'
    test_method = getattr(TestPreview, name)
    for count in range(1,times+1):
        for browser in browser_list:
            new_name = "{name}_{browser}".format(name=name, browser=browser.safe_name())
            if times > 1:
                new_name+= "-{}".format(count)
            new_function = lambda instance, browser_to_use=browser: test_method(instance, browser_to_use)
            new_function.__name__ = new_name
            setattr(TestPreview, new_name, new_function)
    delattr(TestPreview, name)


if BROWSERS_TO_TRY:
    rewrite_for_all_browsers(BROWSERS_TO_TRY, TEST_REPETITIONS)

if __name__ == '__main__':
    main()

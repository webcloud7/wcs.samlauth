from bs4 import BeautifulSoup
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.app.testing import TEST_USER_NAME
from plone.app.testing import TEST_USER_PASSWORD
from plone.testing.zope import Browser
from unittest import TestCase
from wcs.samlauth.testing import SAMLAUTH_FUNCTIONAL_TESTING
from wcs.samlauth.utils import install_plugin
import operator
import transaction
import requests


class FunctionalTesting(TestCase):
    layer = SAMLAUTH_FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        self.idp_metadata_url = 'http://localhost:8000/realms/saml-test/protocol/saml/descriptor'

    def grant(self, *roles):
        setRoles(self.portal, TEST_USER_ID, list(roles))
        transaction.commit()

    def get_browser(self, logged_in=True):
        browser = Browser(self.layer['app'])
        browser.handleErrors = False

        if logged_in:
            browser.open(self.portal.absolute_url() + '/login_form')
            browser.getControl(name='__ac_name').value = TEST_USER_NAME
            browser.getControl(name='__ac_password').value = TEST_USER_PASSWORD
            browser.getControl(name='buttons.login').click()
        return browser

    def _create_plugin(self):
        install_plugin()

    def _find_content(self, data, query, method='select_one'):
        soup = BeautifulSoup(data, 'html.parser')
        find = operator.methodcaller(method, query)
        return find(soup)

    def _login_keycloak_test_user(self):
        login_form = requests.get(self.plugin.absolute_url() + '/sls')
        url_login = self._find_content(login_form.content, 'form').attrs['action']
        login_acs = requests.post(
            url_login,
            data={'username': ' testuser@webcloud7.ch', 'password': '12345'},
            cookies=login_form.cookies
        )
        url_acs = self._find_content(login_acs.content, 'form').attrs['action']
        input_elements = self._find_content(login_acs.content, 'input[type=hidden]', 'select')
        auth_redirect = requests.post(
            url_acs,
            data={element.attrs['name']: element.attrs['value'] for element in input_elements},
            cookies=login_acs.cookies,
            allow_redirects=False
        )
        session_cookie = auth_redirect.cookies
        url = auth_redirect.headers['Location']
        return session_cookie, url

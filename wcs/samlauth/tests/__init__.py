from bs4 import BeautifulSoup
from onelogin.saml2.utils import OneLogin_Saml2_Utils
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.app.testing import TEST_USER_NAME
from plone.app.testing import TEST_USER_PASSWORD
from plone.testing.zope import Browser
from unittest import TestCase
from wcs.samlauth.testing import SAMLAUTH_FUNCTIONAL_TESTING
from wcs.samlauth.utils import install_plugin
from wcs.samlauth.utils import PLUGIN_ID
import json
import operator
import os
import requests
import transaction


class FunctionalTesting(TestCase):
    layer = SAMLAUTH_FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        self.idp_metadata_url = 'http://localhost:8000/realms/saml-test/protocol/saml/descriptor'

        self._create_plugin()
        self.plugin = getattr(self.portal.acl_users, PLUGIN_ID)

    def tearDown(self):
        super().tearDown()
        self.portal.acl_users.manage_delObjects([PLUGIN_ID])

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

    def setup_realm(self, filename='saml-test-realm.json'):
        self.layer['delete_realm']()
        self.layer['create_realm'](filename=filename)

    def setup_sp_certificate(self):
        settings_sp = json.loads(self.plugin.getProperty('settings_sp'))

        cert_path = os.path.join(os.path.dirname(__file__), 'assets', 'sp.cer')
        with open(cert_path, 'r') as cert:
            settings_sp['sp']['x509cert'] = OneLogin_Saml2_Utils.format_cert(cert.read(), heads=False)

        private_key_path = os.path.join(os.path.dirname(__file__), 'assets', 'sp_private_key')
        with open(private_key_path, 'r') as private_key:
            settings_sp['sp']['privateKey'] = OneLogin_Saml2_Utils.format_private_key(private_key.read(), heads=False)

        self.plugin.manage_changeProperties(settings_sp=json.dumps(settings_sp))
        transaction.commit()

    def restore_default_realm(self):
        self.layer['delete_realm']()
        self.layer['create_realm'](filename='saml-test-realm.json')

    def fetch_metadata_from_idp(self):
        self.browser = self.get_browser()
        self.browser.open(self.plugin.absolute_url() + '/idp_metadata')
        self.browser.getControl(
            name='form.widgets.metadata_url').value = self.idp_metadata_url
        self.browser.getControl(name='form.buttons.get_and_store').click()

    def _create_plugin(self):
        install_plugin()
        transaction.commit()

    def _find_content(self, data, query, method='select_one'):
        soup = BeautifulSoup(data, 'html.parser')
        find = operator.methodcaller(method, query)
        return find(soup)

    def _login_keycloak_test_user(self, came_from=None, url=None):
        if url is None:
            url = self.plugin.absolute_url() + '/sls'

        if came_from:
            url += '?came_from=' + came_from
        login_form = requests.get(url)
        assert login_form.url.startswith('http://localhost:8000/realms/saml-test/protocol/saml'), (
            'Expect a redirect to keycloak, but got: ' + login_form.url)
        assert bool(self._find_content(login_form.content, 'form')), 'Expect a form element'
        url_login = self._find_content(login_form.content, 'form').attrs['action']
        login_acs = requests.post(
            url_login,
            data={'username': 'testuser@webcloud7.ch', 'password': '12345'},
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
        assert 'Location' in auth_redirect.headers, 'Expect a redirect'
        url = auth_redirect.headers['Location']
        return session_cookie, url

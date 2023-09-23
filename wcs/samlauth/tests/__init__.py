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

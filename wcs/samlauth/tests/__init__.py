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

    sample_metadata = {
        "idp": {
            "entityId": "http://localhost:8000/realms/saml-test",
            "singleSignOnService": {
                "url": "http://localhost:8000/realms/saml-test/protocol/saml",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
            },
            "singleLogoutService": {
                "url": "http://localhost:8000/realms/saml-test/protocol/saml",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
            },
            "x509cert": "MIICoTCCAYkCBgGKiYJnnTANBgkqhkiG9w0BAQsFADAUMRIwEAYDVQQDDAlzYW1sLXRlc3QwHhcNMjMwOTEyMTMwNzE5WhcNMzMwOTEyMTMwODU5WjAUMRIwEAYDVQQDDAlzYW1sLXRlc3QwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQDIspTdiy9B25Y+F5aXA9E99RZO0f1d86Cfo8Ye2QsWYlAREjzIHx2JXSgXFVJ3ntlYFOzD9GCWBwRkdGOq/c4pkahoLDenXhBvMK3uxQv6VZiwD/gSyMzkkRi9FnfnCoCvNaspyJ9qC8hqHxGnte75zlukE1M+RDwJIxBL1Ud7IKjCYpLtIbSOz3ako4V/mQD6r1v/D7q19omDdgd2/eX5wPiajfT/RNZztKDlce3PG2I9KsRiYsTiyysm0qMHTHZUrPstuPGFAUQySnn2to5vgbf88WutP/3LYPYFDxDmhX+cQ/W1aIULKTIYiPdwT8T6b/fjgYFq97Jl3aaP6QxPAgMBAAEwDQYJKoZIhvcNAQELBQADggEBAD0ChKcNddXltjASRgsnmVYCOpUIGhCZ3cmNmp5bz6RUur2TlPDYKIxjKtA1lpECqOrGGz4qFa8Do7uPbAnvxtyesj+Iph7ASC+ppJx65HObemteDasHEh/jVjRBSGuCDZuHcbpOZn7TvgKCyr4iwiZhUwWrUJRvsG7kIbk+6JoUVgLib6fFaXeNgrogutejfoYtAZoHg+OJCQFscEfFFCi9E7y1spylJAphtNR0ja2P7GoQZqzdmnMaZFt+7FD7n6N1puzrP/FuLqyWLYwel2gARZa+zO4AxRu3pWKVLPi7MiMNu+k67VJ1uNw6whoK/tRkvmQRzamAHG86JmXk3jo="
        },
        "security": {
            "authnRequestsSigned": "true"
        },
        "sp": {
            "NameIDFormat": "urn:oasis:names:tc:SAML:2.0:nameid-format:persistent"
        }
    }

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

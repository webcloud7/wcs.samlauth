from plone import api
from wcs.samlauth.tests import FunctionalTesting
import requests
import transaction


class TestLogout(FunctionalTesting):

    def setUp(self):
        super().setUp()
        self.grant('Manager')
        transaction.commit()

        self.browser = self.get_browser()
        self.browser.open(self.plugin.absolute_url() + '/idp_metadata')
        self.browser.getControl(
            name='form.widgets.metadata_url').value = self.idp_metadata_url
        self.browser.getControl(name='form.buttons.get_and_store').click()

    def test_idp_initiated_logout(self):
        session, url = self._login_keycloak_test_user()
        self.assertTrue(session.get('__ac'), 'Expect a plone session')

        logout_response = requests.get(self.plugin.absolute_url() + '/logout',
                                       cookies=session)

        self.assertEqual(api.portal.get().absolute_url(), logout_response.url)
        self.assertIsNone(logout_response.cookies.get('__ac'), 'Expect no plone session')

        self.assertIn(
            'You are now logged out.',
            self._find_content(logout_response.content, '.statusmessage').text
        )

        # Make sure we also don't have a IDP session anymore
        login_form = requests.get(self.plugin.absolute_url() + '/sls')
        self.assertTrue(
            login_form.url.startswith('http://localhost:8000/realms/saml-test/protocol/saml'),
            'Expect a redirect to keycloak, but got: ' + login_form.url
        )

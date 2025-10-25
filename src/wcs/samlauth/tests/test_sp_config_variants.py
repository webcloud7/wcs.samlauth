from wcs.samlauth.tests import FunctionalTesting
import requests
import transaction
import json


class TestLoginWithDifferentSpConfigVariants(FunctionalTesting):

    def setUp(self):
        super().setUp()
        self.grant('Manager')

        self.browser = self.get_browser()
        self.browser.open(self.plugin.absolute_url() + '/idp_metadata')
        self.browser.getControl(
            name='form.widgets.metadata_url').value = self.idp_metadata_url
        self.browser.getControl(name='form.buttons.get_and_store').click()

    def test_non_strict_mode(self):
        """ This mode basically ignores all security settings and
        only verifies the idp certificate, do not use in production.
        Details check `OneLogin_Saml2_Response` class.
        """

        settings = json.loads(self.plugin.getProperty('advanced'))
        settings['security']['wantAssertionsSigned'] = True
        self.plugin.manage_changeProperties(advanced=json.dumps(settings))
        transaction.commit()

        with self.assertRaises(AssertionError):
            self._login_keycloak_test_user()

        settings['strict'] = False
        self.plugin.manage_changeProperties(advanced=json.dumps(settings))
        transaction.commit()
        session, url = self._login_keycloak_test_user()
        self.assertTrue(session.get('__ac'), 'Expect a plone session')

    def test_sp_config_error(self):
        settings = json.loads(self.plugin.getProperty('advanced'))
        settings['security']['logoutRequestSigned'] = True
        self.plugin.manage_changeProperties(advanced=json.dumps(settings))
        transaction.commit()

        login_form = requests.get(self.plugin.absolute_url() + '/sls')
        self.assertEqual(
            b'SAML SP configuration error: Invalid dict settings: sp_cert_not_found_and_required',
            login_form.content
        )

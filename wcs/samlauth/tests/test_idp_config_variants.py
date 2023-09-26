from onelogin.saml2.utils import OneLogin_Saml2_Utils
from wcs.samlauth.tests import FunctionalTesting
import json
import os
import requests
import transaction


class TestLoginWithDifferentIdpConfigVariants(FunctionalTesting):

    def setUp(self):
        super().setUp()
        self.grant('Manager')

        self.layer['delete_realm']()
        self.layer['create_realm'](filename='saml-test-realm-sp-signature.json')

        self.browser = self.get_browser()
        self.browser.open(self.plugin.absolute_url() + '/idp_metadata')
        self.browser.getControl(
            name='form.widgets.metadata_url').value = self.idp_metadata_url
        self.browser.getControl(name='form.buttons.get_and_store').click()

    def tearDown(self):
        super().tearDown()
        self.layer['delete_realm']()
        self.layer['create_realm'](filename='saml-test-realm.json')

    def _setup_sp_cert(self):
        settings_sp = json.loads(self.plugin.getProperty('settings_sp'))

        cert_path = os.path.join(os.path.dirname(__file__), 'assets', 'sp.cer')
        with open(cert_path, 'r') as cert:
            settings_sp['sp']['x509cert'] = OneLogin_Saml2_Utils.format_cert(cert.read(), heads=False)

        private_key_path = os.path.join(os.path.dirname(__file__), 'assets', 'sp_private_key')
        with open(private_key_path, 'r') as private_key:
            settings_sp['sp']['privateKey'] = OneLogin_Saml2_Utils.format_private_key(private_key.read(), heads=False)

        self.plugin.manage_changeProperties(settings_sp=json.dumps(settings_sp))

        settings = json.loads(self.plugin.getProperty('advanced'))
        settings['security']['authnRequestsSigned'] = True
        self.plugin.manage_changeProperties(advanced=json.dumps(settings))
        transaction.commit()

    def test_idp_expects_sp_cert(self):
        """Test with SP certificate"""
        self._setup_sp_cert()
        session, url = self._login_keycloak_test_user()
        self.assertTrue(session.get('__ac'), 'Expect a plone session')

    def test_do_not_login_without_client_cert(self):
        with self.assertRaises():
            self._login_keycloak_test_user()

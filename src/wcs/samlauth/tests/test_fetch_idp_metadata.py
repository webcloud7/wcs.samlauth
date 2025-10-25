from wcs.samlauth.tests import FunctionalTesting
import json
import requests
import io


class TestIdpMetadata(FunctionalTesting):

    def setUp(self):
        super().setUp()
        self.grant('Manager')
        self.browser = self.get_browser()

    def test_fetch_idp_metadata(self):
        """ We expect to find something like this in the idp metadata endppoint

        :: json
            {
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

        """
        self.browser.open(self.plugin.absolute_url() + '/idp_metadata')
        self.assertEqual(self.browser._response._status, '200 OK')
        self.browser.getControl(name='form.widgets.metadata_url').value = 'invalid_url'
        self.browser.getControl(name='form.buttons.get').click()

        error_element = self._find_content(self.browser.contents, '.invalid-feedback')
        self.assertEqual('Please enter a valid URL.', error_element.text)

        self.browser.getControl(
            name='form.widgets.metadata_url').value = self.idp_metadata_url
        self.browser.getControl(name='form.buttons.get').click()

        code_element = self._find_content(self.browser.contents, '.idp-data code')
        idp_data = json.loads(code_element.text)['idp']
        self.assertEqual(
            'http://localhost:8000/realms/saml-test',
            idp_data['entityId']
        )
        self.assertEqual(
            'http://localhost:8000/realms/saml-test/protocol/saml',
            idp_data['singleSignOnService']['url']
        )
        self.assertEqual(
            'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect',
            idp_data['singleSignOnService']['binding']
        )
        self.assertEqual(
            'http://localhost:8000/realms/saml-test/protocol/saml',
            idp_data['singleLogoutService']['url']
        )
        self.assertEqual(
            'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect',
            idp_data['singleLogoutService']['binding']
        )
        self.assertIn('x509cert', idp_data, 'Expext a cert in idp data')

        sp_data = json.loads(code_element.text)['sp']
        self.assertEqual('urn:oasis:names:tc:SAML:2.0:nameid-format:persistent',
                         sp_data['NameIDFormat'])

    def test_upload_metadata(self):
        xml = io.BytesIO(requests.get(self.idp_metadata_url).content).read()
        self.browser.open(self.plugin.absolute_url() + '/idp_metadata')
        self.assertEqual(self.browser._response._status, '200 OK')
        file_ctl = self.browser.getControl(name="form.widgets.metadata_file")
        file_ctl.add_file(xml, "applocation/xml", "metadata.xml")
        self.browser.getControl(name='form.buttons.get').click()

        code_element = self._find_content(self.browser.contents, '.idp-data code')
        idp_data = json.loads(code_element.text)['idp']
        self.assertEqual(
            'http://localhost:8000/realms/saml-test',
            idp_data['entityId']
        )
        self.assertEqual(
            'http://localhost:8000/realms/saml-test/protocol/saml',
            idp_data['singleSignOnService']['url']
        )
        self.assertEqual(
            'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect',
            idp_data['singleSignOnService']['binding']
        )
        self.assertEqual(
            'http://localhost:8000/realms/saml-test/protocol/saml',
            idp_data['singleLogoutService']['url']
        )
        self.assertEqual(
            'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect',
            idp_data['singleLogoutService']['binding']
        )
        self.assertIn('x509cert', idp_data, 'Expext a cert in idp data')

        sp_data = json.loads(code_element.text)['sp']
        self.assertEqual('urn:oasis:names:tc:SAML:2.0:nameid-format:persistent',
                         sp_data['NameIDFormat'])        

    def test_save_idp_and_sp_data(self):
        self.browser.open(self.plugin.absolute_url() + '/idp_metadata')
        self.browser.getControl(
            name='form.widgets.metadata_url').value = self.idp_metadata_url
        self.browser.getControl(name='form.buttons.get').click()

        code_element = self._find_content(self.browser.contents, '.idp-data code')
        idp_data = json.loads(code_element.text)['idp']
        sp_data = json.loads(code_element.text)['sp']

        self.browser.getControl(name='form.buttons.get_and_store').click()

        metadata = self.plugin.load_settings()
        self.assertEqual(idp_data['entityId'], metadata['idp']['entityId'])
        self.assertDictEqual(
            idp_data['singleSignOnService'],
            metadata['idp']['singleSignOnService']
        )
        self.assertDictEqual(
            idp_data['singleLogoutService'],
            metadata['idp']['singleSignOnService']
        )
        self.assertEqual(idp_data['x509cert'], metadata['idp']['x509cert'])

        self.assertEqual(sp_data['NameIDFormat'],
                         metadata['sp']['NameIDFormat'])

    def test_advanced_settings_are_updated(self):
        """ Keycloak by default sends WantAuthnRequestsSigned=true, which needs
        to be reflected in the security part. We want to handle this manually.
        So check for no changes there
        """
        metadata = self.plugin.load_settings()
        old_value = metadata['security']['authnRequestsSigned']
        self.assertFalse(old_value, 'Old value should be false')

        self.browser.open(self.plugin.absolute_url() + '/idp_metadata')
        self.browser.getControl(
            name='form.widgets.metadata_url').value = self.idp_metadata_url
        self.browser.getControl(name='form.buttons.get_and_store').click()

        self.assertFalse(
            self.plugin.load_settings()['security']['authnRequestsSigned'],
            'New value should be false as well.'
        )

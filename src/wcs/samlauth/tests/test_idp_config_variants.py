from cryptography import x509 as crypto_x509
from cryptography.x509.oid import NameOID
from plone import api
from plone.app.testing import TEST_USER_ID
from wcs.samlauth.tests import FunctionalTesting
from wcs.samlauth.tests.user_property_adapters import OverrideUserPropertiesMutator
from wcs.samlauth.tests.user_property_adapters import PhoneUserPropertiesMutator
from zope.component import getGlobalSiteManager
import base64
import json
import transaction


class TestLoginWithSpSignature(FunctionalTesting):

    def setUp(self):
        super().setUp()
        self.grant('Manager')
        self.setup_realm(filename='saml-test-realm-sp-signature.json')
        self.fetch_metadata_from_idp()

    def tearDown(self):
        super().tearDown()
        self.restore_default_realm()

    def _setup_sp_cert_and_configure(self):
        self.setup_sp_certificate()

        settings = json.loads(self.plugin.getProperty('advanced'))
        settings['security']['authnRequestsSigned'] = True
        self.plugin.manage_changeProperties(advanced=json.dumps(settings))
        transaction.commit()

    def test_idp_expects_sp_cert(self):
        """Test with SP certificate"""
        self._setup_sp_cert_and_configure()
        session, url = self._login_keycloak_test_user()
        self.assertTrue(session.get('__ac'), 'Expect a plone session')

    def test_no_login_without_client_cert(self):
        with self.assertRaises(AssertionError):
            self._login_keycloak_test_user()


class TestLoginWithSpSignatureAndSignedMetadata(FunctionalTesting):
    def setUp(self):
        super().setUp()
        self.grant('Manager')
        self.setup_realm(filename='saml-test-realm-sp-signature-metadata.json')
        self.fetch_metadata_from_idp()

    def tearDown(self):
        super().tearDown()
        self.restore_default_realm()

    def _setup_sp_cert_and_configure(self):
        self.setup_sp_certificate()

        settings = json.loads(self.plugin.getProperty('advanced'))
        settings['security']['authnRequestsSigned'] = True
        settings['security']['signMetadata'] = True
        self.plugin.manage_changeProperties(advanced=json.dumps(settings))
        transaction.commit()

    def test_idp_expects_sp_cert_and_signed_metadata(self):
        """Test with SP certificate"""
        self._setup_sp_cert_and_configure()
        session, url = self._login_keycloak_test_user()
        self.assertTrue(session.get('__ac'), 'Expect a plone session')

    def test_no_login_without_client_cert(self):
        with self.assertRaises(AssertionError):
            self._login_keycloak_test_user()


class TestAdfsSamlRequest(FunctionalTesting):
    def test_adfs_saml_flag(self):
        login_view = self.plugin.restrictedTraverse('sls')
        self.assertFalse(
            login_view._prepare_request().get('lowercase_urlencoding'),
            'lowercase_urlencoding should not be present'
        )

        self.plugin.manage_changeProperties(adfs_as_idp=True)
        login_view = self.plugin.restrictedTraverse('sls')
        self.assertTrue(
            login_view._prepare_request().get('lowercase_urlencoding'),
            'lowercase_urlencoding should be there')


class TestLoginWithCustomAttr(FunctionalTesting):
    def setUp(self):
        super().setUp()
        self.grant('Manager')

        ptool = api.portal.get_tool('portal_memberdata')
        ptool.manage_addProperty("phone", "", "string")
        transaction.commit()
        self.setup_realm(filename='saml-test-realm-custom-attr.json')
        self.fetch_metadata_from_idp()
        self.site = getGlobalSiteManager()
        self.site.registerAdapter(factory=PhoneUserPropertiesMutator, name='phone')
        self.site.registerAdapter(factory=OverrideUserPropertiesMutator, name='override')

    def tearDown(self):
        super().tearDown()
        self.restore_default_realm()
        self.site.unregisterAdapter(factory=PhoneUserPropertiesMutator, name='phone')
        self.site.unregisterAdapter(factory=OverrideUserPropertiesMutator, name='override')

    def test_login_with_custom_attr(self):
        session, url = self._login_keycloak_test_user()
        self.assertTrue(session.get('__ac'), 'Expect a plone session')
        transaction.begin()

        user = tuple(filter(
            lambda user: user.getId() != TEST_USER_ID,
            api.portal.get_tool('portal_membership').listMembers())
        )[0]
        self.assertEqual(user.getProperty('phone'), '123456789')

    def test_override_fullname_with_phone(self):
        session, url = self._login_keycloak_test_user()
        self.assertTrue(session.get('__ac'), 'Expect a plone session')
        transaction.begin()

        user = tuple(filter(
            lambda user: user.getId() != TEST_USER_ID,
            api.portal.get_tool('portal_membership').listMembers())
        )[0]
        self.assertEqual(user.getProperty('fullname'), '123456789')


class TestGenerateSpCertificate(FunctionalTesting):
    """Unit tests for generate_sp_certificate()."""

    def setUp(self):
        super().setUp()
        self.grant('Manager')

    def test_generates_and_stores_cert_and_key(self):
        """Certificate and private key must be stored in settings_sp after generation."""
        self.plugin.generate_sp_certificate()

        settings = json.loads(self.plugin.getProperty('settings_sp'))
        self.assertTrue(settings['sp']['x509cert'])
        self.assertTrue(settings['sp']['privateKey'])

    def test_generated_cert_is_valid_x509(self):
        """The generated certificate must be a valid X.509 certificate."""
        self.plugin.generate_sp_certificate()

        cert_b64 = json.loads(self.plugin.getProperty('settings_sp'))['sp']['x509cert']
        cert = crypto_x509.load_der_x509_certificate(base64.b64decode(cert_b64))
        cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
        self.assertIn('saml', cn)

    def test_generate_overwrites_existing_certificate(self):
        """Calling generate_sp_certificate() twice produces different certificates."""
        self.plugin.generate_sp_certificate()
        cert_first = json.loads(self.plugin.getProperty('settings_sp'))['sp']['x509cert']

        self.plugin.generate_sp_certificate()
        cert_second = json.loads(self.plugin.getProperty('settings_sp'))['sp']['x509cert']

        self.assertNotEqual(cert_first, cert_second)


class TestLoginWithGeneratedSpCertificate(FunctionalTesting):
    """E2E test: login with authnRequestsSigned=True using a dynamically generated SP certificate.

    The generated certificate is registered with Keycloak via the admin API so
    that Keycloak can verify the signed AuthnRequest.
    """

    def setUp(self):
        super().setUp()
        self.grant('Manager')
        self.setup_realm(filename='saml-test-realm-sp-signature.json')
        self.fetch_metadata_from_idp()

    def tearDown(self):
        super().tearDown()
        self.restore_default_realm()

    def test_login_with_generated_certificate_and_authn_signed(self):
        self.plugin.generate_sp_certificate()
        generated_cert = json.loads(self.plugin.getProperty('settings_sp'))['sp']['x509cert']

        self.register_sp_cert_with_keycloak(generated_cert, signature_algorithm='RSA_SHA256')

        settings = json.loads(self.plugin.getProperty('advanced'))
        settings['security']['authnRequestsSigned'] = True
        settings['security']['signatureAlgorithm'] = (
            'http://www.w3.org/2001/04/xmldsig-more#rsa-sha256'
        )
        self.plugin.manage_changeProperties(advanced=json.dumps(settings))
        transaction.commit()

        session, url = self._login_keycloak_test_user()
        self.assertTrue(session.get('__ac'), 'Expect a plone session')

    def test_no_login_without_matching_certificate(self):
        """Login fails when Keycloak has a different cert than what the SP is using."""
        self.plugin.generate_sp_certificate()

        settings = json.loads(self.plugin.getProperty('advanced'))
        settings['security']['authnRequestsSigned'] = True
        self.plugin.manage_changeProperties(advanced=json.dumps(settings))
        transaction.commit()

        # Keycloak still has the static test cert → signature verification will fail
        with self.assertRaises(AssertionError):
            self._login_keycloak_test_user()

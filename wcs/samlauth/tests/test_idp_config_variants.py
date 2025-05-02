from plone import api
from plone.app.testing import TEST_USER_ID
from wcs.samlauth.tests import FunctionalTesting
from wcs.samlauth.tests.user_property_adapters import OverrideUserPropertiesMutator
from wcs.samlauth.tests.user_property_adapters import PhoneUserPropertiesMutator
from zope.component import getGlobalSiteManager
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

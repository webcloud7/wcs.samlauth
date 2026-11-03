from unittest import TestCase
from wcs.samlauth.plugin import SamlAuthPlugin


class FakeAuth:
    """Minimal stand-in for OneLogin_Saml2_Auth after process_response.

    Attributes mirror a Lepida FedERa response: only a few attributes
    carry a FriendlyName.
    """

    def __init__(self, nameid='LEPI0000241137'):
        self.nameid = nameid
        self.attributes = {
            'CodiceFiscale': ['MCAMRA71S11C704W'],
            'authenticatingAuthority': ['Lepida ID--TEST--'],
            'authenticationMethod': ['Primo Livello SPID'],
            'cognome': ['fiori'],
            'emailAddressPersonale': ['user@example.org'],
            'nome': ['mino'],
            'spidCode': ['LEPI0000241137'],
        }
        self.friendlyname_attributes = {
            'Gestore di credenziali': ['Lepida ID--TEST--'],
            'Metodo di autenticazione': ['Primo Livello SPID'],
        }

    def get_nameid(self):
        return self.nameid

    def get_attributes(self):
        return self.attributes

    def get_friendlyname_attributes(self):
        return self.friendlyname_attributes


class TestUserInfo(TestCase):

    def setUp(self):
        self.plugin = SamlAuthPlugin('saml')
        self.auth = FakeAuth()

    def test_userinfo_contains_attributes_by_name_and_friendly_name(self):
        userinfo = self.plugin._get_userinfo(self.auth)

        self.assertEqual(['mino'], userinfo['nome'])
        self.assertEqual(['fiori'], userinfo['cognome'])
        self.assertEqual(['MCAMRA71S11C704W'], userinfo['CodiceFiscale'])
        self.assertEqual(['Lepida ID--TEST--'], userinfo['Gestore di credenziali'])

    def test_friendly_name_wins_on_conflict(self):
        self.auth.attributes['email'] = ['by-name@example.org']
        self.auth.friendlyname_attributes['email'] = ['by-friendly-name@example.org']

        userinfo = self.plugin._get_userinfo(self.auth)

        self.assertEqual(['by-friendly-name@example.org'], userinfo['email'])

    def test_auth_attributes_are_not_modified(self):
        self.plugin._get_userinfo(self.auth)

        self.assertNotIn('Gestore di credenziali', self.auth.attributes)

    def test_attributes_without_friendly_names(self):
        self.auth.friendlyname_attributes = {}

        userinfo = self.plugin._get_userinfo(self.auth)

        self.assertEqual(self.auth.attributes, userinfo)


class TestUserId(TestCase):

    def setUp(self):
        self.plugin = SamlAuthPlugin('saml')
        self.auth = FakeAuth()
        self.userinfo = self.plugin._get_userinfo(self.auth)

    def test_nameid_is_default_user_id(self):
        self.assertEqual(
            'LEPI0000241137', self.plugin._get_user_id(self.auth, self.userinfo))

    def test_user_id_from_configured_attribute(self):
        self.plugin.manage_changeProperties(userid_attribute='CodiceFiscale')

        self.assertEqual(
            'MCAMRA71S11C704W', self.plugin._get_user_id(self.auth, self.userinfo))

    def test_user_id_from_friendly_name_attribute(self):
        self.plugin.manage_changeProperties(userid_attribute='Gestore di credenziali')

        self.assertEqual(
            'Lepida ID--TEST--', self.plugin._get_user_id(self.auth, self.userinfo))

    def test_missing_user_id_attribute_does_not_fall_back_to_nameid(self):
        self.plugin.manage_changeProperties(userid_attribute='fiscalNumber')

        with self.assertLogs('wcs.samlauth.plugin', level='ERROR') as logs:
            self.assertEqual('', self.plugin._get_user_id(self.auth, self.userinfo))
        self.assertIn("'fiscalNumber'", logs.output[0])

    def test_empty_user_id_attribute_value_is_rejected(self):
        self.auth.attributes['CodiceFiscale'] = ['  ']
        self.plugin.manage_changeProperties(userid_attribute='CodiceFiscale')
        userinfo = self.plugin._get_userinfo(self.auth)

        with self.assertLogs('wcs.samlauth.plugin', level='ERROR'):
            self.assertEqual('', self.plugin._get_user_id(self.auth, userinfo))

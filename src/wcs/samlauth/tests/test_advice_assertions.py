from base64 import b64encode
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from onelogin.saml2.response import OneLogin_Saml2_Response
from onelogin.saml2.settings import OneLogin_Saml2_Settings
from onelogin.saml2.utils import OneLogin_Saml2_Utils
from unittest import TestCase
from wcs.samlauth.saml import AdviceAwareResponse
from wcs.samlauth.saml import SamlAuth
import os


ASSETS = os.path.join(os.path.dirname(__file__), 'assets')
SP_ENTITY_ID = 'https://sp.example.org/metadata'
ACS_URL = 'https://sp.example.org/acs'
IDP_ENTITY_ID = 'https://idp.example.org/metadata'

RESPONSE = (
    '<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"'
    ' xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"'
    ' ID="_response" Version="2.0" IssueInstant="{now}" Destination="{acs}">'
    '<saml:Issuer>{idp}</saml:Issuer>'
    '{extensions}'
    '<samlp:Status>'
    '<samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/>'
    '</samlp:Status>'
    '{assertions}'
    '</samlp:Response>'
)

ASSERTION = (
    '<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"'
    ' ID="{id}" Version="2.0" IssueInstant="{now}">'
    '<saml:Issuer>{idp}</saml:Issuer>'
    '<saml:Subject>'
    '<saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified">'
    'user</saml:NameID>'
    '<saml:SubjectConfirmation Method="urn:oasis:names:tc:SAML:2.0:cm:bearer">'
    '<saml:SubjectConfirmationData NotOnOrAfter="{later}" Recipient="{acs}"/>'
    '</saml:SubjectConfirmation>'
    '</saml:Subject>'
    '<saml:Conditions NotBefore="{before}" NotOnOrAfter="{later}">'
    '<saml:AudienceRestriction><saml:Audience>{sp}</saml:Audience>'
    '</saml:AudienceRestriction>'
    '</saml:Conditions>'
    '{advice}'
    '<saml:AuthnStatement AuthnInstant="{now}"><saml:AuthnContext>'
    '<saml:AuthnContextClassRef>'
    'urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport'
    '</saml:AuthnContextClassRef>'
    '</saml:AuthnContext></saml:AuthnStatement>'
    '<saml:AttributeStatement>'
    '<saml:Attribute Name="email"><saml:AttributeValue>user@example.org'
    '</saml:AttributeValue></saml:Attribute>'
    '</saml:AttributeStatement>'
    '</saml:Assertion>'
)

# Upstream assertions embedded by the IdP proxy (e.g. Lepida FedERa).
ADVICE = (
    '<saml:Advice>'
    '<saml:Assertion ID="_advice1" Version="2.0" IssueInstant="{now}">'
    '<saml:Issuer>https://upstream.example.org</saml:Issuer>'
    '<saml:AttributeStatement>'
    '<saml:Attribute Name="email"><saml:AttributeValue>evil@example.org'
    '</saml:AttributeValue></saml:Attribute>'
    '</saml:AttributeStatement>'
    '</saml:Assertion>'
    '<saml:Assertion ID="_advice2" Version="2.0" IssueInstant="{now}">'
    '<saml:Issuer>https://upstream.example.org</saml:Issuer>'
    '</saml:Assertion>'
    '</saml:Advice>'
)

STRAY_ASSERTION = (
    '<samlp:Extensions>'
    '<saml:Assertion ID="_stray" Version="2.0" IssueInstant="{now}">'
    '<saml:Issuer>https://attacker.example.org</saml:Issuer>'
    '</saml:Assertion>'
    '</samlp:Extensions>'
)


def _read_asset(name):
    with open(os.path.join(ASSETS, name)) as asset:
        return asset.read()


class TestAssertionsInAdvice(TestCase):

    def setUp(self):
        # xmlsec needs PEM headers to load the key pair.
        self.cert = OneLogin_Saml2_Utils.format_cert(_read_asset('sp.cer'))
        self.key = OneLogin_Saml2_Utils.format_private_key(_read_asset('sp_private_key'))
        self.settings = OneLogin_Saml2_Settings({
            'strict': True,
            'sp': {
                'entityId': SP_ENTITY_ID,
                'assertionConsumerService': {'url': ACS_URL},
            },
            'idp': {
                'entityId': IDP_ENTITY_ID,
                'singleSignOnService': {'url': 'https://idp.example.org/sso'},
                # The test IdP signs with the SP test key pair.
                'x509cert': self.cert,
            },
            'security': {'wantAssertionsSigned': True},
        })
        self.request_data = {
            'https': 'on',
            'http_host': 'sp.example.org',
            'script_name': '/acs',
        }

        now = datetime.now(timezone.utc)
        self.values = {
            'now': self._format(now),
            'before': self._format(now - timedelta(minutes=2)),
            'later': self._format(now + timedelta(minutes=5)),
            'acs': ACS_URL,
            'sp': SP_ENTITY_ID,
            'idp': IDP_ENTITY_ID,
        }

    def _format(self, date):
        return date.strftime('%Y-%m-%dT%H:%M:%SZ')

    def _assertion(self, id_='_assertion', advice=True):
        assertion = ASSERTION.format(
            id=id_,
            advice=ADVICE.format(**self.values) if advice else '',
            **self.values,
        )
        signed = OneLogin_Saml2_Utils.add_sign(assertion, self.key, self.cert)
        return signed.decode() if isinstance(signed, bytes) else signed

    def _response(self, assertions, extensions=''):
        xml = RESPONSE.format(
            assertions=''.join(assertions),
            extensions=extensions,
            **self.values,
        )
        return b64encode(xml.encode()).decode()

    def test_upstream_response_class_rejects_advice_assertions(self):
        response = OneLogin_Saml2_Response(
            self.settings, self._response([self._assertion()]))

        self.assertFalse(response.is_valid(self.request_data))
        self.assertEqual(
            'SAML Response must contain 1 assertion', response.get_error())

    def test_advice_assertions_are_accepted(self):
        response = AdviceAwareResponse(
            self.settings, self._response([self._assertion()]))

        self.assertTrue(response.is_valid(self.request_data), response.get_error())
        self.assertEqual('user', response.get_nameid())
        # Attributes come from the top-level assertion only.
        self.assertEqual(
            {'email': ['user@example.org']}, response.get_attributes())

    def test_response_without_advice_is_still_accepted(self):
        response = AdviceAwareResponse(
            self.settings, self._response([self._assertion(advice=False)]))

        self.assertTrue(response.is_valid(self.request_data), response.get_error())

    def test_two_top_level_assertions_are_rejected(self):
        response = AdviceAwareResponse(self.settings, self._response([
            self._assertion('_assertion1', advice=False),
            self._assertion('_assertion2', advice=False),
        ]))

        self.assertFalse(response.validate_num_assertions())
        self.assertFalse(response.is_valid(self.request_data))
        self.assertEqual(
            'SAML Response must contain 1 assertion', response.get_error())

    def test_assertion_outside_advice_is_rejected(self):
        response = AdviceAwareResponse(self.settings, self._response(
            [self._assertion()],
            extensions=STRAY_ASSERTION.format(**self.values),
        ))

        self.assertFalse(response.validate_num_assertions())
        self.assertFalse(response.is_valid(self.request_data))

    def test_saml_auth_uses_advice_aware_response(self):
        request_data = dict(
            self.request_data,
            post_data={'SAMLResponse': self._response([self._assertion()])},
        )
        auth = SamlAuth(request_data, self.settings)
        auth.process_response()

        self.assertEqual([], auth.get_errors(), auth.get_last_error_reason())
        self.assertTrue(auth.is_authenticated())
        self.assertEqual('user', auth.get_nameid())

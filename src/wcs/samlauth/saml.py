from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.response import OneLogin_Saml2_Response
from onelogin.saml2.xml_utils import OneLogin_Saml2_XML


class AdviceAwareResponse(OneLogin_Saml2_Response):
    """SAML Response that tolerates assertions nested in saml:Advice.

    Some IdP proxies (e.g. Lepida FedERa) embed the upstream assertions
    inside the <saml:Advice> element of the top-level assertion.
    python3-saml counts every assertion in the document (//saml:Assertion)
    and rejects such responses with "SAML Response must contain 1 assertion".

    We still require exactly one top-level assertion (encrypted or not).
    Any other assertion must live inside the Advice of that assertion, so it
    is covered by its signature. Attributes are only read from the top-level
    assertion (see `_query_assertion`), nested ones are ignored.
    """

    TOP_LEVEL_ASSERTIONS = (
        '/samlp:Response/saml:Assertion'
        ' | /samlp:Response/saml:EncryptedAssertion'
    )
    ALL_ASSERTIONS = '//saml:Assertion | //saml:EncryptedAssertion'
    ADVICE_ASSERTIONS = (
        '/samlp:Response/saml:Assertion/saml:Advice//saml:Assertion'
        ' | /samlp:Response/saml:Assertion/saml:Advice//saml:EncryptedAssertion'
    )

    def _has_single_assertion(self, document):
        top_level = OneLogin_Saml2_XML.query(document, self.TOP_LEVEL_ASSERTIONS)
        all_assertions = OneLogin_Saml2_XML.query(document, self.ALL_ASSERTIONS)
        advice = OneLogin_Saml2_XML.query(document, self.ADVICE_ASSERTIONS)
        return (
            len(top_level) == 1
            and len(all_assertions) == len(top_level) + len(advice)
        )

    def validate_num_assertions(self):
        valid = self._has_single_assertion(self.document)
        if self.encrypted:
            valid = valid and self._has_single_assertion(self.decrypted_document)
        return valid


class SamlAuth(OneLogin_Saml2_Auth):
    response_class = AdviceAwareResponse

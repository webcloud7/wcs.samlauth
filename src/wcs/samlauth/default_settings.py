DEFAULT_SP_SETTINGS = """
{
    "sp": {
        // Identifier of the SP entity  (must be a URI) - 
        "entityId": "https://<sp_domain>/metadata/",
        // Specifies info about where and how the <AuthnResponse> message MUST be
        // returned to the requester, in this case our SP.
        "assertionConsumerService": {
            // URL Location where the <Response> from the IdP will be returned
            "url": "https://<sp_domain>/?acs",
            // SAML protocol binding to be used when returning the <Response>
            // message. SAML Toolkit supports this endpoint for the
            // HTTP-POST binding only.
            "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
        },
        // Specifies info about where and how the <Logout Request/Response> message MUST be sent.
        "singleLogoutService": {
            // URL Location where the <LogoutRequest> from the IdP will be sent (IdP-initiated logout)
            "url": "https://<sp_domain>/?sls",
            // URL Location where the <LogoutResponse> from the IdP will sent (SP-initiated logout, reply)
            // OPTIONAL: only specify if different from url parameter
            //"responseUrl": "https://<sp_domain>/?sls",
            // SAML protocol binding to be used when returning the <Response>
            // message. SAML Toolkit supports the HTTP-Redirect binding
            // only for this endpoint.
            "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
        },
        // If you need to specify requested attributes, set a
        // attributeConsumingService. nameFormat, attributeValue and
        // friendlyName can be omitted
        // "attributeConsumingService": {
                // OPTIONAL: only specify if SP requires this.
                // index is an integer which identifies the attributeConsumingService used
                // to the SP. SAML toolkit supports configuring only one attributeConsumingService
                // but in certain cases the SP requires a different value.  Defaults to '1'.
                //"index": '1',
                //"serviceName": "SP test",
                //"serviceDescription": "Test Service",
                //"requestedAttributes": [
                //   {
                //      "name": "",
                //        "isRequired": false,
                //        "nameFormat": "",
                //        "friendlyName": "",
                //        "attributeValue": []
                //    }
        //        ]
        // },
        // Specifies the constraints on the name identifier to be used to
        // represent the requested subject.
        // Take a look on src/onelogin/saml2/constants.py to see the NameIdFormat that are supported.
        "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified",
        // Usually X.509 cert and privateKey of the SP are provided by files placed at
        // the certs folder. But we can also provide them with the following parameters
        "x509cert": "",
        "privateKey": ""

        /*
         * Key rollover
         * If you plan to update the SP X.509cert and privateKey
         * you can define here the new X.509cert and it will be
         * published on the SP metadata so Identity Providers can
         * read them and get ready for rollover.
         */
        // 'x509certNew': '',
    }
}
"""

DEFAULT_IDP_SETTINGS = """
{
    // Identity Provider Data that we want connected with our SP.
    "idp": {
        // Identifier of the IdP entity  (must be a URI)
        "entityId": "https://app.onelogin.com/saml/metadata/<onelogin_connector_id>",
        // SSO endpoint info of the IdP. (Authentication Request protocol)
        "singleSignOnService": {
            // URL Target of the IdP where the Authentication Request Message
            // will be sent.
            "url": "https://app.onelogin.com/trust/saml2/http-post/sso/<onelogin_connector_id>",
            // SAML protocol binding to be used when returning the <Response>
            // message. SAML Toolkit supports the HTTP-Redirect binding
            // only for this endpoint.
            "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
        },
        // SLO endpoint info of the IdP.
        "singleLogoutService": {
            // URL Location where the <LogoutRequest> from the IdP will be sent (IdP-initiated logout)
            "url": "https://app.onelogin.com/trust/saml2/http-redirect/slo/<onelogin_connector_id>",
            // URL Location where the <LogoutResponse> from the IdP will sent (SP-initiated logout, reply)
            // OPTIONAL: only specify if different from url parameter
            "responseUrl": "https://app.onelogin.com/trust/saml2/http-redirect/slo_return/<onelogin_connector_id>",
            // SAML protocol binding to be used when returning the <Response>
            // message. SAML Toolkit supports the HTTP-Redirect binding
            // only for this endpoint.
            "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
        },
        // Public X.509 certificate of the IdP
        "x509cert": "<onelogin_connector_cert>"
        /*
         *  Instead of using the whole X.509cert you can use a fingerprint in order to
         *  validate a SAMLResponse (but you still need the X.509cert to validate LogoutRequest and LogoutResponse using the HTTP-Redirect binding).
         *  But take in mind that the algorithm for the fingerprint should be as strong as the algorithm in a normal certificate signature
         *  (e.g. SHA256 or strong)
         *
         *  (openssl x509 -noout -fingerprint -in "idp.crt" to generate it,
         *  or add for example the -sha256 , -sha384 or -sha512 parameter)
         *
         *  If a fingerprint is provided, then the certFingerprintAlgorithm is required in order to
         *  let the toolkit know which algorithm was used. Possible values: sha1, sha256, sha384 or sha512
         *  'sha1' is the default value.
         *
         *  Notice that if you want to validate any SAML Message sent by the HTTP-Redirect binding, you
         *  will need to provide the whole X.509cert.
         */
        // "certFingerprint": "",
        // "certFingerprintAlgorithm": "sha1",

        /* In some scenarios the IdP uses different certificates for
         * signing/encryption, or is under key rollover phase and
         * more than one certificate is published on IdP metadata.
         * In order to handle that the toolkit offers that parameter.
         * (when used, 'X.509cert' and 'certFingerprint' values are
         * ignored).
         */
        // 'x509certMulti': {
        //      'signing': [
        //          '<cert1-string>'
        //      ],
        //      'encryption': [
        //          '<cert2-string>'
        //      ]
        // }
    }
}
"""


ADVANCED_SETTINGS = """
{
    // If strict is True, then the Python Toolkit will reject unsigned
    // or unencrypted messages if it expects them to be signed or encrypted.
    // Also it will reject the messages if the SAML standard is not strictly
    // followed. Destination, NameId, Conditions ... are validated too.
    "strict": true,

    // Enable debug mode (outputs errors).
    "debug": true,

    // Security settings
    "security": {

        /** signatures and encryptions offered **/

        // Indicates that the nameID of the <samlp:logoutRequest> sent by this SP
        // will be encrypted.
        "nameIdEncrypted": false,

        // Indicates whether the <samlp:AuthnRequest> messages sent by this SP
        // will be signed.  [Metadata of the SP will offer this info]
        "authnRequestsSigned": false,

        // Indicates whether the <samlp:logoutRequest> messages sent by this SP
        // will be signed.
        "logoutRequestSigned": false,

        // Indicates whether the <samlp:logoutResponse> messages sent by this SP
        // will be signed.
        "logoutResponseSigned": false,

        /* Sign the Metadata
         * false || true (use sp certs) || {
         *                                    "keyFileName": "metadata.key",
         *                                    "certFileName": "metadata.crt"
         *                                 }
        */
        "signMetadata": false,

        /** signatures and encryptions required **/

        // Indicates a requirement for the <samlp:Response>, <samlp:LogoutRequest>
        // and <samlp:LogoutResponse> elements received by this SP to be signed.
        "wantMessagesSigned": false,

        // Indicates a requirement for the <saml:Assertion> elements received by
        // this SP to be signed. [Metadata of the SP will offer this info]
        "wantAssertionsSigned": false,

        // Indicates a requirement for the <saml:Assertion>
        // elements received by this SP to be encrypted.
        "wantAssertionsEncrypted": false,

        // Indicates a requirement for the NameID element on the SAMLResponse
        // received by this SP to be present.
        "wantNameId": true,

        // Indicates a requirement for the NameID received by
        // this SP to be encrypted.
        "wantNameIdEncrypted": false,

        // Indicates a requirement for the AttributeStatement element
        "wantAttributeStatement": true,

        // Authentication context.
        // Set to false and no AuthContext will be sent in the AuthNRequest,
        // Set true or don't present this parameter and you will get an AuthContext 'exact' 'urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport'
        // Set an array with the possible auth context values: array ('urn:oasis:names:tc:SAML:2.0:ac:classes:Password', 'urn:oasis:names:tc:SAML:2.0:ac:classes:X509'),
        "requestedAuthnContext": true,
    // Allows the authn comparison parameter to be set, defaults to 'exact' if the setting is not present.
        "requestedAuthnContextComparison": "exact",
        // Set to true to check that the AuthnContext(s) received match(es) the requested.
        "failOnAuthnContextMismatch": false,

        // In some environment you will need to set how long the published metadata of the Service Provider gonna be valid.
        // is possible to not set the 2 following parameters (or set to null) and default values will be set (2 days, 1 week)
        // Provide the desire TimeStamp, for example 2015-06-26T20:00:00Z
        "metadataValidUntil": null,
        // Provide the desire Duration, for example PT518400S (6 days)
        "metadataCacheDuration": null,

        // If enabled, URLs with single-label-domains will
        // be allowed and not rejected by the settings validator (Enable it under Docker/Kubernetes/testing env, not recommended on production)
        "allowSingleLabelDomains": false,

        // Algorithm that the toolkit will use on signing process. Options:
        //    'http://www.w3.org/2000/09/xmldsig#rsa-sha1'
        //    'http://www.w3.org/2000/09/xmldsig#dsa-sha1'
        //    'http://www.w3.org/2001/04/xmldsig-more#rsa-sha256'
        //    'http://www.w3.org/2001/04/xmldsig-more#rsa-sha384'
        //    'http://www.w3.org/2001/04/xmldsig-more#rsa-sha512'
        "signatureAlgorithm": "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256",

        // Algorithm that the toolkit will use on digest process. Options:
        //    'http://www.w3.org/2000/09/xmldsig#sha1'
        //    'http://www.w3.org/2001/04/xmlenc#sha256'
        //    'http://www.w3.org/2001/04/xmldsig-more#sha384'
        //    'http://www.w3.org/2001/04/xmlenc#sha512'
        "digestAlgorithm": "http://www.w3.org/2001/04/xmlenc#sha256",

        // Specify if you want the SP to view assertions with duplicated Name or FriendlyName attributes to be valid
        // Defaults to false if not specified
        "allowRepeatAttributeName": true,

        // If the toolkit receive a message signed with a
        // deprecated algorithm (defined at the constant class)
        // will raise an error and reject the message
        "rejectDeprecatedAlgorithm": true
    },

    // Contact information template, it is recommended to suply a
    // technical and support contacts.
    "contactPerson": {
        "technical": {
            "givenName": "technical_name",
            "emailAddress": "technical@example.com"
        },
        "support": {
            "givenName": "support_name",
            "emailAddress": "support@example.com"
        }
    },

    // Organization information template, the info in en_US lang is
    // recommended, add more if required.
    "organization": {
        "en-US": {
            "name": "sp_test",
            "displayname": "SP test",
            "url": "http://sp.example.com"
        }
    }
}
"""

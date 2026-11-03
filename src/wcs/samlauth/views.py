from onelogin.saml2.errors import OneLogin_Saml2_Error
from plone import api
from plone.protect.interfaces import IDisableCSRFProtection
from Products.Five.browser import BrowserView
from Products.statusmessages.interfaces import IStatusMessage
from urllib.parse import quote
from urllib.parse import urlparse
from wcs.samlauth.saml import SamlAuth
from zExceptions import BadRequest
from zope.interface import alsoProvides
import json
import logging


LOGGER = logging.getLogger(__name__)
SAML_AUTHN_REQUEST_COOKIE_NAME = '__saml'


class BaseSamlView(BrowserView):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.saml_request = self._prepare_request()
        self.context._maybe_refresh_metadata()
        self.settings = self.context.load_settings()
        self._update_settings()

    def _prepare_request(self):
        url = urlparse(self.request.URL)
        request = {
            'https': 'on' if url.scheme == 'https' else 'off',
            'http_host': url.netloc,
            'script_name': url.path,
            'get_data': self.request.form.copy(),
            'post_data': self.request.form.copy()
        }
        # if using ADFS as IdP, https://github.com/onelogin/python-saml/pull/144
        # 'lowercase_urlencoding': True,
        if self.context.getProperty('adfs_as_idp'):
            request['lowercase_urlencoding'] = True
        return request

    def _update_settings(self):
        """Update SP settings with dynamic values"""
        plugin_url = self.context.absolute_url()
        sp = self.settings['sp']
        sp['entityId'] = plugin_url + '/metadata'
        sp['assertionConsumerService']['url'] = plugin_url + '/acs'
        sp['singleLogoutService']['url'] = plugin_url + '/slo'


class LoginView(BaseSamlView):
    def __call__(self):
        try:
            auth = SamlAuth(self.saml_request, self.settings)
        except OneLogin_Saml2_Error as error:
            LOGGER.error(str(error))
            self.request.response.setHeader('X-Theme-Disabled', '1')
            self.request.response.setHeader('Content-Type', 'text/plain')
            self.request.response.setStatus(400)
            if self.settings['debug']:
                return f'SAML SP configuration error: {str(error)}'
            return 'SAML SP configuration not valid, please check logs'

        return_url = self.request.get('came_from', None)
        if not return_url:
            return_url = api.portal.get().absolute_url()
        login_url = auth.login(return_to=return_url)

        if auth.get_last_request_id() and self.context.getProperty('validate_authn_request', False):
            self.request.response.setCookie(
                SAML_AUTHN_REQUEST_COOKIE_NAME,
                auth.get_last_request_id()
            )
        return self.request.RESPONSE.redirect(login_url)


class CallbackView(BaseSamlView):
    def __call__(self):
        alsoProvides(self.request, IDisableCSRFProtection)
        auth = SamlAuth(self.saml_request, self.settings)
        request_id = None

        if SAML_AUTHN_REQUEST_COOKIE_NAME in self.request:
            request_id = self.request[SAML_AUTHN_REQUEST_COOKIE_NAME]

        auth.process_response(request_id=request_id)
        errors = auth.get_errors()
        if len(errors) != 0 and not auth.is_authenticated():
            LOGGER.error(errors)
            LOGGER.error(auth.get_last_error_reason())
            raise BadRequest

        if request_id:
            self.request.response.expireCookie(SAML_AUTHN_REQUEST_COOKIE_NAME)

        self.context.remember_identity(auth)

        return self.request.response.redirect(self.get_redirect_url())

    def get_redirect_url(self):
        url = api.portal.get().absolute_url()
        if 'RelayState' in self.request.form:
            relay_state = self.request.form['RelayState']
            allowed_hosts = [self.saml_request['http_host']]
            allowed_hosts.extend(
                list(self.context.getProperty('allowed_redirect_hosts', ()))
            )
            if urlparse(relay_state).netloc in allowed_hosts:
                url = relay_state

        create_api_session = self.context.getProperty("create_api_session")
        include_api_token = self.context.getProperty("include_api_token_in_redirect")
        if include_api_token and create_api_session:
            token = self.request.RESPONSE.cookies.get('auth_token', None)
            if token:
                url += f'?auth_token={token["value"]}'
        return url


class IdpLogoutView(BaseSamlView):
    def __call__(self):
        auth = SamlAuth(self.saml_request, self.settings)

        def _logout():
            mt = api.portal.get_tool('portal_membership')
            mt.logoutUser(self.request)
            # Handle JWT token logout

        auth.process_slo(delete_session_cb=_logout)
        return self.request.RESPONSE.redirect(api.portal.get().absolute_url() + '/logged-out')


class LogoutView(BaseSamlView):
    def __call__(self):
        auth = SamlAuth(self.saml_request, self.settings)
        logout_url = auth.logout(return_to=api.portal.get().absolute_url())
        return self.request.RESPONSE.redirect(logout_url)


MD_NS = 'urn:oasis:names:tc:SAML:2.0:metadata'
DS_NS = 'http://www.w3.org/2000/09/xmldsig#'

ENCRYPTION_METHODS = [
    'http://www.w3.org/2009/xmlenc11#aes256-gcm',
    'http://www.w3.org/2001/04/xmlenc#aes256-cbc',
    'http://www.w3.org/2001/04/xmlenc#rsa-oaep-mgf1p',
]


def _postprocess_metadata(metadata):
    """Fix ACS index and add encryption KeyDescriptor with EncryptionMethod elements."""
    from lxml import etree

    root = etree.fromstring(metadata if isinstance(metadata, bytes) else metadata.encode())

    spsso = root.find('{%s}SPSSODescriptor' % MD_NS)
    if spsso is None:
        return etree.tostring(root, encoding='unicode')

    # 1. Fix AssertionConsumerService index: set to 0
    for acs in spsso.iter('{%s}AssertionConsumerService' % MD_NS):
        acs.set('index', '0')

    # 2. Ensure encryption KeyDescriptor exists with EncryptionMethod elements.
    #    If one already exists (e.g. added by the library), just add the methods.
    #    Otherwise, copy the cert from the signing KeyDescriptor and add a new one.
    enc_kd = None
    signing_kd = None
    for kd in spsso.findall('{%s}KeyDescriptor' % MD_NS):
        use = kd.get('use')
        if use == 'encryption':
            enc_kd = kd
        elif use == 'signing':
            signing_kd = kd

    if enc_kd is None and signing_kd is not None:
        # Build encryption KeyDescriptor after the signing one, reusing its cert
        enc_kd = etree.Element('{%s}KeyDescriptor' % MD_NS, use='encryption')
        key_info = signing_kd.find('{%s}KeyInfo' % DS_NS)
        if key_info is not None:
            import copy
            enc_kd.append(copy.deepcopy(key_info))
        signing_kd.addnext(enc_kd)

    if enc_kd is not None:
        existing_algs = {em.get('Algorithm') for em in enc_kd.findall('{%s}EncryptionMethod' % MD_NS)}
        for alg in ENCRYPTION_METHODS:
            if alg not in existing_algs:
                etree.SubElement(enc_kd, '{%s}EncryptionMethod' % MD_NS, Algorithm=alg)

    return etree.tostring(root, encoding='unicode')


class MetadataView(BaseSamlView):
    def __call__(self):
        self.request.response.setHeader('X-Theme-Disabled', '1')
        auth = SamlAuth(self.saml_request, self.settings)
        saml_settings = auth.get_settings()
        metadata = saml_settings.get_sp_metadata()
        errors = saml_settings.validate_metadata(metadata)

        if len(errors) == 0:
            metadata = _postprocess_metadata(metadata)
            self.request.response.setHeader('Content-Type', 'application/xml')
            return metadata
        else:
            return "Error found on Metadata: %s" % (', '.join(errors))


class RequireLoginView(BrowserView):
    """Our version of the require-login view from Plone.

    Our challenge plugin redirects here.
    Note that the plugin has no way of knowing if you are authenticated:
    its code is called before this is known.
    I think.
    """

    def __call__(self):
        if api.user.is_anonymous():
            # context is our PAS plugin
            url = self.context.absolute_url() + '/sls'
            came_from = self.request.get('came_from', None)
            if came_from:
                url += f'?came_from={quote(came_from)}'
        else:
            url = api.portal.get().absolute_url()
            url += '/insufficient-privileges'

        self.request.response.redirect(url)


class GenerateSpCertificateView(BrowserView):
    """Generate a self-signed SP certificate and private key, store them in
    settings_sp, then redirect back to the IDP metadata management page.
    """

    def __call__(self):
        alsoProvides(self.request, IDisableCSRFProtection)
        try:
            self.context.generate_sp_certificate()
            IStatusMessage(self.request).addStatusMessage(
                'SP certificate generated successfully. '
                'Register the updated SP metadata with your IDP.',
                type='info',
            )
        except Exception as e:
            LOGGER.error('Failed to generate SP certificate: %s', e)
            IStatusMessage(self.request).addStatusMessage(
                f'Failed to generate SP certificate: {e}',
                type='error',
            )
        return self.request.response.redirect(
            self.context.absolute_url() + '/idp_metadata'
        )


class RefreshIdPMetadataView(BrowserView):
    """Trigger an immediate IDP metadata refresh from the stored metadata_url."""

    def __call__(self):
        alsoProvides(self.request, IDisableCSRFProtection)
        self.request.response.setHeader('X-Theme-Disabled', '1')
        self.request.response.setHeader('Content-Type', 'application/json')

        url = self.context.getProperty('metadata_url', '')
        if not url:
            self.request.response.setStatus(400)
            return json.dumps({'status': 'error', 'message': 'No metadata URL configured'})

        success, result = self.context.refresh_metadata()
        if success:
            return json.dumps({'status': 'ok', 'refreshed_at': result, 'url': url})
        else:
            self.request.response.setStatus(500)
            return json.dumps({'status': 'error', 'message': result, 'url': url})

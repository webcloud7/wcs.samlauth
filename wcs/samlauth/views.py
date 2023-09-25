from onelogin.saml2.auth import OneLogin_Saml2_Auth
from plone import api
from Products.Five.browser import BrowserView
from urllib.parse import urlparse
from zExceptions import BadRequest
import logging


LOGGER = logging.getLogger(__name__)
SAML_AUTHN_REQUEST_COOKIE_NAME = '__saml'


class BaseSamlView(BrowserView):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.saml_request = self._prepare_request()
        self.settings = self._load_settings()
        self._update_settings()

    def _prepare_request(self):
        url = urlparse(self.request.URL)
        return {
            'https': 'on' if url.scheme == 'https' else 'off',
            'http_host': url.netloc,
            'script_name': self.request.PATH_INFO,
            'get_data': self.request.form.copy(),
            # Uncomment if using ADFS as IdP, https://github.com/onelogin/python-saml/pull/144
            # 'lowercase_urlencoding': True,
            'post_data': self.request.form.copy()
        }

    def _load_settings(self):
        return self.context.load_and_clean_settings()

    def _update_settings(self):
        """Update SP settings with dynamic values"""
        plugin_url = self.context.absolute_url()
        sp = self.settings['sp']
        sp['entityId'] = plugin_url + '/metadata'
        sp['assertionConsumerService']['url'] = plugin_url + '/acs'
        sp['singleLogoutService']['url'] = plugin_url + '/slo'


class LoginView(BaseSamlView):
    def __call__(self):
        auth = OneLogin_Saml2_Auth(self.saml_request, self.settings)
        if auth.get_last_request_id():
            self.request.response.setCookie(
                SAML_AUTHN_REQUEST_COOKIE_NAME,
                auth.get_last_request_id()
            )
        return self.request.RESPONSE.redirect(auth.login())


class CallbackView(BaseSamlView):
    def __call__(self):
        auth = OneLogin_Saml2_Auth(self.saml_request, self.settings)
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
        return self.request.response.redirect(api.portal.get().absolute_url())


class LogoutView(BaseSamlView):
    def __call__(self):
        auth = OneLogin_Saml2_Auth(self.saml_request, self.settings)

        def _logout():
            mt = api.portal.get_tool('portal_membership')
            mt.logoutUser(self.request)
            # Handle JWT token logout

        auth.process_slo(delete_session_cb=_logout)
        return self.request.RESPONSE.redirect(api.portal.get().absolute_url() + '/logged_out')


class MetadataView(BaseSamlView):
    def __call__(self):
        self.request.response.setHeader('X-Theme-Disabled', '1')
        auth = OneLogin_Saml2_Auth(self.saml_request, self.settings)
        saml_settings = auth.get_settings()
        metadata = saml_settings.get_sp_metadata()
        errors = saml_settings.validate_metadata(metadata)
        
        if len(errors) == 0:
            self.request.response.setHeader('Content-Type', 'application/xml')
            return metadata
        else:
            return "Error found on Metadata: %s" % (', '.join(errors))

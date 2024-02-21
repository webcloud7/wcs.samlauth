from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.errors import OneLogin_Saml2_Error
from plone import api
from plone.protect.interfaces import IDisableCSRFProtection
from Products.Five.browser import BrowserView
from urllib.parse import quote
from urllib.parse import urlparse
from zExceptions import BadRequest
from zope.interface import alsoProvides
import logging


LOGGER = logging.getLogger(__name__)
SAML_AUTHN_REQUEST_COOKIE_NAME = '__saml'


class BaseSamlView(BrowserView):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.saml_request = self._prepare_request()
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
            auth = OneLogin_Saml2_Auth(self.saml_request, self.settings)
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

        return self.request.response.redirect(self.get_redirect_url())

    def get_redirect_url(self):
        if 'RelayState' in self.request.form:
            relay_state = self.request.form['RelayState']
            allowed_hosts = [self.saml_request['http_host']]
            allowed_hosts.extend(
                list(self.context.getProperty('allowed_redirect_hosts', ()))
            )
            if urlparse(relay_state).netloc in allowed_hosts:
                return relay_state
        return api.portal.get().absolute_url()


class IdpLogoutView(BaseSamlView):
    def __call__(self):
        auth = OneLogin_Saml2_Auth(self.saml_request, self.settings)

        def _logout():
            mt = api.portal.get_tool('portal_membership')
            mt.logoutUser(self.request)
            # Handle JWT token logout

        auth.process_slo(delete_session_cb=_logout)
        return self.request.RESPONSE.redirect(api.portal.get().absolute_url() + '/logged-out')


class LogoutView(BaseSamlView):
    def __call__(self):
        auth = OneLogin_Saml2_Auth(self.saml_request, self.settings)
        logout_url = auth.logout(return_to=api.portal.get().absolute_url())
        return self.request.RESPONSE.redirect(logout_url)


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

from AccessControl.class_init import InitializeClass
from AccessControl.SecurityInfo import ClassSecurityInfo
from onelogin.saml2.idp_metadata_parser import OneLogin_Saml2_IdPMetadataParser
from plone import api
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from Products.PluggableAuthService.interfaces.plugins import IAuthenticationPlugin
from Products.PluggableAuthService.interfaces.plugins import IChallengePlugin
from Products.PluggableAuthService.interfaces.plugins import IUserAdderPlugin
from Products.PluggableAuthService.plugins.BasePlugin import BasePlugin
from Products.PluggableAuthService.utils import classImplements
from secrets import choice
from wcs.samlauth.default_settings import ADVANCED_SETTINGS
from wcs.samlauth.default_settings import DEFAULT_IDP_SETTINGS
from wcs.samlauth.default_settings import DEFAULT_SP_SETTINGS
from wcs.samlauth.interfaces import ISAMLUserPropertiesMutator
from wcs.samlauth.utils import clean_for_json
from ZODB.POSException import ConflictError
from zope.component import getAdapters
from zope.interface import Interface
import json
import logging
import string


logger = logging.getLogger(__name__)
PWCHARS = string.ascii_letters + string.digits + string.punctuation

manage_addSamlAuthPluginForm = PageTemplateFile("templates/add_plugin", globals())


def manage_addSamlAuthPlugin(self, id_, title='', RESPONSE=None):
    """Add a Saml2 Auth plugin.
    """
    plugin = SamlAuthPlugin(id_, title)
    self._setObject(plugin.getId(), plugin)

    if RESPONSE is not None:
        RESPONSE.redirect("manage_workspace")


class ISamlAuthPlugin(Interface):
    """Marker interfaces for saml plugins"""


class SamlAuthPlugin(BasePlugin):
    """Saml Auth plugin.
    """

    meta_type = "SAML Auth plugin"
    security = ClassSecurityInfo()

    create_session = True
    create_api_session = False
    create_user = True
    validate_authn_request = False
    allowed_redirect_hosts = ()
    settings_sp = json.dumps(json.loads(clean_for_json(DEFAULT_SP_SETTINGS)), indent=4)
    settings_idp = json.dumps(json.loads(clean_for_json(DEFAULT_IDP_SETTINGS)), indent=4)
    advanced = json.dumps(json.loads(clean_for_json(ADVANCED_SETTINGS)), indent=4)
    adfs_as_idp = False

    _properties = (
        dict(id='create_session', label='Create Plone Session', type='boolean', mode='w'),
        dict(id='create_api_session', label='Create API Session', type='boolean', mode='w'),
        dict(id='create_user', label='Create User', type='boolean', mode='w'),
        dict(id='validate_authn_request', label='Validate AuthN requests via cookie', type='boolean', mode='w'),
        dict(id='allowed_redirect_hosts', label='Allowed hosts to redirect to', type='lines', mode='w'),
        dict(id='settings_sp', label='SP (plone) Settings', type='text', mode='w'),
        dict(id='settings_idp', label='IDP Settings', type='text', mode='w'),
        dict(id='advanced', label='Advanced', type='text', mode='w'),
        dict(id='adfs_as_idp', label='Check this box if ADFS is the IDP', type='boolean', mode='w'),
    )

    def __init__(self, id_, title=None):
        self._setId(id_)
        self.title = title

    def remember_identity(self, auth):
        user_id = auth.get_nameid()
        userinfo = auth.get_friendlyname_attributes()
        if not userinfo:
            userinfo = auth.get_attributes()
        pas = self._getPAS()
        if pas is None:
            return

        user = pas.getUserById(user_id)
        if self.getProperty("create_user"):
            if user is None:
                userAdders = self.plugins.listPlugins(IUserAdderPlugin)
                if not userAdders:
                    raise NotImplementedError(
                        "I wanted to make a new user, but"
                        " there are no PAS plugins active"
                        " that can make users."
                    )

                # Add the user to the first IUserAdderPlugin that works:
                user = None
                for _, curAdder in userAdders:
                    if curAdder.doAddUser(user_id, self._generatePassword()):
                        # Assign a dummy password. It'll never be used;.
                        user = self._getPAS().getUser(user_id)
                        try:
                            membershipTool = api.portal.get_tool("portal_membership")
                            if not membershipTool.getHomeFolder(user_id):
                                membershipTool.createMemberArea(user_id)
                        except (ConflictError, KeyboardInterrupt):
                            raise
                        except Exception:  # nosec B110
                            # Silently ignored exception, but seems fine here.
                            # Logging would likely generate too much noise,
                            # depending on your setup.
                            # https://bandit.readthedocs.io/en/1.7.4/plugins/b110_try_except_pass.html
                            pass
                        self._updateUserProperties(user, userinfo)
                        break
            else:
                self._updateUserProperties(user, userinfo)

        if user and self.getProperty("create_session"):
            self._setup_plone_session(user_id)
        if user and self.getProperty("create_api_session"):
            self._setup_jwt_session(user_id, user)

    def _updateUserProperties(self, user, userinfo):
        """Update the given user properties from the set of credentials.
        This is utilised when first creating a user, and to update
        their information when logging in again later.
        """
        properties = {}
        mutators = list(getAdapters((self, api.portal.get().REQUEST), ISAMLUserPropertiesMutator))
        mutators.sort(key=lambda adapter: adapter[1]._order)
        for mutator in mutators:
            try:
                mutator[1].mutate(user, userinfo, properties)
            except Exception as e:
                logger.error(f"Error in user properties mutator: {e}")
                continue
        if properties:
            user.setProperties(**properties)

    def _generatePassword(self):
        """Return a obfuscated password never used for login"""
        return "".join([choice(PWCHARS) for ii in range(40)])  # nosec B311

    def _setup_plone_session(self, user_id):
        """Set up authentication session (__ac cookie) with plone.session.

        Only call this when self.create_session is True.
        """
        pas = self._getPAS()
        if pas is None:
            return
        if "session" not in pas:
            return
        info = pas._verifyUser(pas.plugins, user_id=user_id)
        if info is None:
            logger.debug("No user found matching header. Will not set up session.")
            return
        response = self.REQUEST.RESPONSE
        pas.session._setupSession(user_id, response)
        logger.debug("Done setting up session/ticket for %s" % user_id)

    def _setup_jwt_session(self, user_id, user):
        """Set up JWT authentication session (auth_token cookie).

        Only call this when self.create_api_session is True.
        """
        authenticators = self.plugins.listPlugins(IAuthenticationPlugin)
        plugin = None
        for id_, authenticator in authenticators:
            if authenticator.meta_type == "JWT Authentication Plugin":
                plugin = authenticator
                break
        if plugin:
            payload = {}
            payload["fullname"] = user.getProperty("fullname")
            token = plugin.create_token(user.getId(), data=payload)
            response = self.REQUEST.RESPONSE
            response.setCookie("auth_token", token, path="/")

    def _fetch_metadata(self, url):
        idp_data = OneLogin_Saml2_IdPMetadataParser.parse_remote(url)
        return idp_data

    def _update_metadata(self, new_data):
        settings = self.load_settings()
        merged_data = OneLogin_Saml2_IdPMetadataParser.merge_settings(
            settings, new_data
        )
        return merged_data

    def load_settings(self):
        settings = json.loads(self.getProperty('advanced'))
        settings.update(json.loads(self.getProperty('settings_sp')))
        settings.update(json.loads(self.getProperty('settings_idp')))
        return settings

    def store(self, metadata):
        settings_idp = metadata.pop('idp')
        settings_sp = metadata.pop('sp')
        self.manage_changeProperties(
            **{
                'settings_idp': json.dumps({'idp': settings_idp}, indent=4),
                'settings_sp': json.dumps({'sp': settings_sp}, indent=4),
            }
        )

    def challenge(self, request, response):
        """Go to the login view of the PAS plugin
        """
        logger.info(f'Challenge. Came from {request.URL}')
        url = f"{self.absolute_url()}/require_login?came_from={request.URL}"
        response.redirect(url, lock=1)
        return True


InitializeClass(SamlAuthPlugin)

classImplements(
    SamlAuthPlugin,
    ISamlAuthPlugin,
    IChallengePlugin,
)

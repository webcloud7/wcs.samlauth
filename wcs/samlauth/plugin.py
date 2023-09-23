from AccessControl.class_init import InitializeClass
from AccessControl.SecurityInfo import ClassSecurityInfo
from contextlib import contextmanager
from plone import api
from plone.protect.utils import safeWrite
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from Products.PluggableAuthService.interfaces.plugins import IAuthenticationPlugin
from Products.PluggableAuthService.interfaces.plugins import IChallengePlugin
from Products.PluggableAuthService.interfaces.plugins import IUserAdderPlugin
from Products.PluggableAuthService.plugins.BasePlugin import BasePlugin
from Products.PluggableAuthService.utils import classImplements
from secrets import choice
from wcs.samlauth.default_settings import ADVANCED_SETTINGS
from wcs.samlauth.default_settings import DEFAULT_SETTINGS
from wcs.samlauth.default_settings import DEFAULT_SP_SETTINGS
from wcs.samlauth.default_settings import DEFAULT_IDP_SETTINGS
from ZODB.POSException import ConflictError
from zope.interface import Interface
import itertools
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
    settings = DEFAULT_SETTINGS
    settings_sp = DEFAULT_SP_SETTINGS
    settings_idp = DEFAULT_IDP_SETTINGS
    advanced = ADVANCED_SETTINGS

    _properties = (
        dict(id='create_session', label='Create Plone Session', type='bool', mode='w'),
        dict(id='create_api_session', label='Create API Session', type='bool', mode='w'),
        dict(id='create_user', label='Create User', type='bool', mode='w'),
        dict(id='settings', label='Settings', type='text', mode='w'),
        dict(id='settings_sp', label='Settings', type='text', mode='w'),
        dict(id='settings_idp', label='Settings', type='text', mode='w'),
        dict(id='advanced', label='Advanced', type='text', mode='w'),
    )

    def remember_identity(self, auth):
        user_id = auth.get_nameid()
        userinfo = auth.get_attributes()
        pas = self._getPAS()
        if pas is None:
            return
        user = pas.getUserById(user_id)
        if self.getProperty("create_user"):
            if user is None:
                with safe_write(self.REQUEST):
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
                with safe_write(self.REQUEST):
                    self._updateUserProperties(user, userinfo)

        if user and self.getProperty("create_session"):
            self._setupTicket(user_id)
        if user and self.getProperty("create_api_session"):
            self._setupJWTTicket(user_id, user)

    def _updateUserProperties(self, user, userinfo):
        """Update the given user properties from the set of credentials.
        This is utilised when first creating a user, and to update
        their information when logging in again later.
        """
        # TODO: modificare solo se ci sono dei cambiamenti sui dati ?
        # TODO: mettere in config il mapping tra metadati che arrivano da oidc e properties su plone
        # TODO: warning nel caso non vengono tornati dati dell'utente
        userProps = {}
        if "email" in userinfo:
            userProps["email"] = userinfo["email"]
        if "given_name" in userinfo and "family_name" in userinfo:
            userProps["fullname"] = "{} {}".format(
                userinfo["given_name"], userinfo["family_name"]
            )
        elif "name" in userinfo and "family_name" in userinfo:
            userProps["fullname"] = "{} {}".format(
                userinfo["name"], userinfo["family_name"]
            )
        # userProps[LAST_UPDATE_USER_PROPERTY_KEY] = time.time()
        if userProps:
            user.setProperties(**userProps)

    def _generatePassword(self):
        """Return a obfuscated password never used for login"""
        return "".join([choice(PWCHARS) for ii in range(40)])  # nosec B311

    def _setupTicket(self, user_id):
        """Set up authentication ticket (__ac cookie) with plone.session.

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
        request = self.REQUEST
        response = request["RESPONSE"]
        pas.session._setupSession(user_id, response)
        logger.debug("Done setting up session/ticket for %s" % user_id)

    def _setupJWTTicket(self, user_id, user):
        """Set up JWT authentication ticket (auth_token cookie).

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
            request = self.REQUEST
            response = request["RESPONSE"]
            # TODO: take care of path, cookiename and domain options ?
            response.setCookie("auth_token", token, path="/")

    def challenge(self, request, response):
        """Assert via the response that credentials will be gathered.

        For IChallengePlugin.

        Takes a REQUEST object and a RESPONSE object.

        Must return True if it fired, False/None otherwise.

        Note: if you are not logged in, and go to the login form,
        everything will still work, and you will not be challenged.
        A challenge is only tried when you are unauthorized.
        """
        # Go to the login view of the PAS plugin.
        logger.info("Challenge. Came from %s", request.URL)
        url = "{}/require_login?came_from={}".format(self.absolute_url(), request.URL)
        response.redirect(url, lock=1)
        return True


InitializeClass(SamlAuthPlugin)

classImplements(
    SamlAuthPlugin,
    ISamlAuthPlugin,
    IChallengePlugin,
)


# https://github.com/collective/Products.AutoUserMakerPASPlugin/blob/master/Products/AutoUserMakerPASPlugin/auth.py
@contextmanager
def safe_write(request):
    """Disable CSRF protection of plone.protect for a block of code.
    Inside the context manager objects can be written to without any
    restriction. The context manager collects all touched objects
    and marks them as safe write."""
    # We used 'set' here before, but that could lead to:
    # TypeError: unhashable type: 'PersistentMapping'
    objects_before = _registered_objects(request)
    yield
    objects_after = _registered_objects(request)
    for obj in objects_after:
        if obj not in objects_before:
            safeWrite(obj, request)


def _registered_objects(request):
    """Collect all objects part of a pending write transaction."""
    app = request.PARENTS[-1]
    return list(
        itertools.chain.from_iterable(
            [
                conn._registered_objects
                # skip the 'temporary' connection since it stores session objects
                # which get written all the time
                for name, conn in app._p_jar.connections.items()
                if name != "temporary"
            ]
        )
    )

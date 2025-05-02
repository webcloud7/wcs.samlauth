from wcs.samlauth.interfaces import ISAMLUserPropertiesMutator
from wcs.samlauth.plugin import ISamlAuthPlugin
from wcs.samlauth.utils import make_string
from zope.component import adapter
from zope.interface import implementer
from zope.interface import Interface


@implementer(ISAMLUserPropertiesMutator)
@adapter(ISamlAuthPlugin, Interface)
class DefaultUserPropertiesMutator:
    """
    Default implementation of user properties mutator.
    """

    _order = 1

    def __init__(self, plugin, request):
        self.plugin = plugin
        self.request = request

    def mutate(self, user, userinfo, properties):
        """
        Mutate the user properties based on the provided userinfo.

        :param user: Plone user object.
        :param userinfo: Dictionary containing user information.
        :param properties: Dictionary containing current user properties
        :return: None. Updates properties by reference
        """
        user_properties = {}
        if "email" in userinfo:
            user_properties["email"] = make_string(userinfo["email"])
        if "givenName" in userinfo and "surname" in userinfo:
            user_properties["fullname"] = "{} {}".format(
                make_string(userinfo["givenName"]), make_string(userinfo["surname"])
            )
        elif "name" in userinfo and "surname" in userinfo:
            user_properties["fullname"] = "{} {}".format(
                make_string(userinfo["name"]), make_string(userinfo["surname"])
            )
        properties.update(user_properties)

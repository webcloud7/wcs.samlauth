from wcs.samlauth.interfaces import ISAMLUserPropertiesMutator
from wcs.samlauth.plugin import ISamlAuthPlugin
from wcs.samlauth.utils import make_string
from zope.component import adapter
from zope.interface import implementer
from zope.interface import Interface


@implementer(ISAMLUserPropertiesMutator)
@adapter(ISamlAuthPlugin, Interface)
class PhoneUserPropertiesMutator:

    _order = 2

    def __init__(self, plugin, request):
        self.plugin = plugin
        self.request = request

    def mutate(self, user, userinfo, properties):
        if "Phone" in userinfo:
            properties["phone"] = make_string(userinfo["Phone"])


@implementer(ISAMLUserPropertiesMutator)
@adapter(ISamlAuthPlugin, Interface)
class OverrideUserPropertiesMutator:
    _order = 2

    def __init__(self, plugin, request):
        self.plugin = plugin
        self.request = request

    def mutate(self, user, userinfo, properties):
        if "Phone" in userinfo:
            properties["fullname"] = make_string(userinfo["Phone"])

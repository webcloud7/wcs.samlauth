from AccessControl.Permissions import manage_users
from Products.PluggableAuthService.PluggableAuthService import registerMultiPlugin
from wcs.samlauth import plugin
from zope.i18nmessageid import MessageFactory


_ = MessageFactory("wcs.samlauth")


def initialize(context):
    """Initializer called when used as a Zope 2 product."""

    registerMultiPlugin(plugin.SamlAuthPlugin.meta_type)

    context.registerClass(
        plugin.SamlAuthPlugin,
        permission=manage_users,
        constructors=(
            plugin.manage_addSamlAuthPluginForm,
            plugin.manage_addSamlAuthPlugin,
        ),
        visibility=None)

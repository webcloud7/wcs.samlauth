from zope.interface import Interface


class ISAMLUserPropertiesMutator(Interface):
    """
    Interface for user properties in SAML authentication.
    """

    def mutate(user, userinfo, properties):
        """
        Mutate the user properties based on the provided userinfo.

        :param user: Plone user object.
        :param userinfo: Dictionary containing user information.
        :param properties: Dictionary containing current user properties
        :return: None. Updates properties by reference
        """

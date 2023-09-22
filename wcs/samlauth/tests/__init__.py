from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from unittest import TestCase
from wcs.samlauth.testing import SAMLAUTH_FUNCTIONAL_TESTING
from wcs.samlauth.utils import install_plugin
import transaction


class FunctionalTesting(TestCase):
    layer = SAMLAUTH_FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        self.request = self.layer['request']

    def grant(self, *roles):
        setRoles(self.portal, TEST_USER_ID, list(roles))
        transaction.commit()

    def _create_plugin(self):
        install_plugin()

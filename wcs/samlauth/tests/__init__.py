from copy import deepcopy
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD
from plone.app.testing import TEST_USER_ID
from plone.dexterity.interfaces import IDexterityFTI
from Products.CMFCore.indexing import processQueue
from unittest import TestCase
from wcs.samlauth.testing import SAMLAUTH_FUNCTIONAL_TESTING
from zope.component import queryUtility
import os
import transaction


class FunctionalTesting(TestCase):
    layer = SAMLAUTH_FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        self.request = self.layer['request']

    def grant(self, *roles):
        setRoles(self.portal, TEST_USER_ID, list(roles))
        transaction.commit()

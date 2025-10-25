from bs4 import BeautifulSoup
from wcs.samlauth.tests import FunctionalTesting
from wcs.samlauth.utils import PLUGIN_ID
import requests
import transaction


class TestSpMetadata(FunctionalTesting):

    def setUp(self):
        super().setUp()

    def test_sp_metadata(self):
        response = requests.get(f'{self.plugin.absolute_url()}/metadata')
        self.assertEqual(200, response.status_code)
        xml = response.content
        self.assertEqual('application/xml', response.headers['Content-Type'])

        soup = BeautifulSoup(xml, "xml")
        self.assertEqual(
            self.plugin.absolute_url() + '/metadata',
            soup.find('md:EntityDescriptor').attrs['entityID']
        )
        self.assertEqual(
            self.plugin.absolute_url() + '/acs',
            soup.find('md:AssertionConsumerService').attrs['Location']
        )
        self.assertEqual(
            self.plugin.absolute_url() + '/slo',
            soup.find('md:SingleLogoutService').attrs['Location']
        )

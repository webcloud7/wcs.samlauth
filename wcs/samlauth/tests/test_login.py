from bs4 import BeautifulSoup
from wcs.samlauth.tests import FunctionalTesting
from wcs.samlauth.utils import PLUGIN_ID
import requests
import transaction


class TestLogin(FunctionalTesting):

    def setUp(self):
        super().setUp()
        self.grant('Manager')
        self._create_plugin()
        self.plugin = getattr(self.portal.acl_users, PLUGIN_ID)
        transaction.commit()

        self.browser = self.get_browser()
        self.browser.open(self.plugin.absolute_url() + '/idp_metadata')
        self.browser.getControl(
            name='form.widgets.metadata_url').value = self.idp_metadata_url
        self.browser.getControl(name='form.buttons.get_and_store').click()

    def test_login(self):

        # 1. Go to login endpoint, which redirects to the keycloak login form
        login_form = requests.get(self.plugin.absolute_url() + '/sls')

        # 2. Fill and submit login form
        url_login = self._find_content(login_form.content, 'form').attrs['action']
        login_acs = requests.post(
            url_login,
            data={'username': ' testuser@webcloud7.ch', 'password': '12345'},
            cookies=login_form.cookies
        )

        # 3. Submit callback (acs) - since there is no JS we do this manually 
        url_acs = self._find_content(login_acs.content, 'form').attrs['action']
        input_elements = self._find_content(login_acs.content, 'input[type=hidden]', 'select')
        auth_redirect = requests.post(
            url_acs,
            data={element.attrs['name']: element.attrs['value'] for element in input_elements},
            cookies=login_acs.cookies,
            allow_redirects=False
        )

        # 4. Get session cookie from redirect and open plone startpage
        self.assertEqual(302, auth_redirect.status_code)
        self.assertEqual(self.portal.absolute_url(), auth_redirect.headers['Location'])

        auth_response = requests.get(auth_redirect.headers['Location'],
                                     cookies=auth_redirect.cookies)
        self.assertTrue(
            self._find_content(auth_response.content, '.userrole-authenticated'),
            'Expect a body class userrole-authenticated'
        )

        # 5. Check if user properties are there as well
        reponse_profile = requests.get(
            self.portal.absolute_url() + '/@@personal-information',
            cookies=auth_redirect.cookies
        )

        self.assertEqual(
            'Test User',
            self._find_content(reponse_profile.content, '#form-widgets-fullname').attrs['value']
        )
        self.assertEqual(
            'testuser@webcloud7.ch',
            self._find_content(reponse_profile.content, '#form-widgets-email').attrs['value']
        )

from plone import api
from plone.app.testing import TEST_USER_ID
from plone.restapi.setuphandlers import install_pas_plugin as install_api_jwt_plugin
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

    def test_user_properties(self):
        self._login_keycloak_test_user()
        transaction.begin()

        self.assertEqual(
            2, len(api.portal.get_tool('portal_membership').listMembers()),
            'Expect 2 users, the test user and the new user from keycloak'
        )

        user = tuple(filter(
            lambda user: user.getId() != TEST_USER_ID,
            api.portal.get_tool('portal_membership').listMembers())
        )[0]

        self.assertEqual('testuser@webcloud7.ch', user.getProperty('email'))
        self.assertEqual('Test User', user.getProperty('fullname'))

    def test_do_not_create_user(self):
        self.plugin.manage_changeProperties(create_user=False)
        transaction.commit()
        self._login_keycloak_test_user()

        transaction.begin()

        self.assertEqual(
            1, len(api.portal.get_tool('portal_membership').listMembers()),
            'Expect 1 user, the test user and the new user from keycloak'
        )

    def test_do_not_create_plone_session(self):
        self.plugin.manage_changeProperties(create_session=False)
        transaction.commit()
        session_cookie, url = self._login_keycloak_test_user()

        self.assertFalse(session_cookie, 'Expect no session cookie')

    def test_create_api_session(self):
        self.plugin.manage_changeProperties(create_api_session=True)
        install_api_jwt_plugin(self.portal)
        transaction.commit()
        session_cookie, url = self._login_keycloak_test_user()

        self.assertTrue(session_cookie, 'Expect session cookie')

        jwt_cookie = session_cookie.get('auth_token')
        self.assertTrue(jwt_cookie, 'Expect api jwt session cookie')

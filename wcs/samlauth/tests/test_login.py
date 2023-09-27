from plone import api
from plone.app.testing import TEST_USER_ID
from plone.restapi.setuphandlers import install_pas_plugin as install_api_jwt_plugin
from wcs.samlauth.tests import FunctionalTesting
from wcs.samlauth.views import SAML_AUTHN_REQUEST_COOKIE_NAME
import requests
import transaction


class TestLogin(FunctionalTesting):

    def setUp(self):
        super().setUp()
        self.grant('Manager')
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

    def test_redirect_after_login(self):
        page = api.content.create(
            container=self.portal,
            id='testpage',
            type='Document',
            title='Testpage'
        )
        session, url = self._login_keycloak_test_user(
            came_from=page.absolute_url()
        )

        self.assertTrue(session.get('__ac'), 'Expect a plone session')
        self.assertEqual(page.absolute_url(), url)

    def test_redirect_to_external_site_not_possible_by_default(self):
        session, url = self._login_keycloak_test_user(
            came_from='https://www.someexternalsite.com'
        )

        self.assertTrue(session.get('__ac'), 'Expect a plone session')
        self.assertEqual(api.portal.get().absolute_url(), url)

    def test_redirect_to_external_with_explicit_allow_host_list(self):
        self.plugin.manage_changeProperties(allowed_redirect_hosts=('www.myfrontend.com', ))
        transaction.commit()
        session, url = self._login_keycloak_test_user(
            came_from='https://www.myfrontend.com/demo'
        )

        self.assertTrue(session.get('__ac'), 'Expect a plone session')
        self.assertEqual('https://www.myfrontend.com/demo', url)

    def test_challenge_plugin(self):
        prefs_url = api.portal.get().absolute_url() + '/@@personal-preferences'
        response_login_page = requests.get(prefs_url)
        self.assertEqual(response_login_page.status_code, 200)
        self.assertTrue(
            response_login_page.url.startswith('http://localhost:8000/realms/saml-test/protocol/saml'),
            'Expect a redirect to keycloak, but got: ' + response_login_page.url)

    def test_login_via_challange(self):
        prefs_url = api.portal.get().absolute_url() + '/@@personal-preferences'
        session, url = self._login_keycloak_test_user(url=prefs_url)
        self.assertTrue(session.get('__ac'), 'Expect a plone session')
        self.assertEqual(prefs_url, url)

    def test_login_and_validate_auth_n_request(self):
        self.plugin.manage_changeProperties(validate_authn_request=True)
        transaction.commit()

        login_form_redirect = requests.get(
            self.plugin.absolute_url() + '/sls',
            allow_redirects=False)
        self.assertIn(SAML_AUTHN_REQUEST_COOKIE_NAME, login_form_redirect.cookies)
        login_form = requests.get(login_form_redirect.headers['Location'])
        url_login = self._find_content(login_form.content, 'form').attrs['action']
        login_acs = requests.post(
            url_login,
            data={'username': ' testuser@webcloud7.ch', 'password': '12345'},
            cookies=login_form.cookies
        )

        url_acs = self._find_content(login_acs.content, 'form').attrs['action']
        input_elements = self._find_content(login_acs.content, 'input[type=hidden]', 'select')
        auth_redirect = requests.post(
            url_acs,
            data={element.attrs['name']: element.attrs['value'] for element in input_elements},
            cookies=login_form_redirect.cookies,
            allow_redirects=False
        )

        assert 'Location' in auth_redirect.headers, 'Expect a redirect'
        self.assertNotIn(SAML_AUTHN_REQUEST_COOKIE_NAME, auth_redirect.cookies)

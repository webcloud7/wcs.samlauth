from plone.app.testing import FunctionalTesting
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import PloneSandboxLayer
from plone.testing import Layer
from plone.testing.zope import installProduct
from plone.testing.zope import WSGI_SERVER_FIXTURE
from zope.configuration import xmlconfig
import logging
import os
import shutil
import subprocess
import sys
import time
import requests


MAX_CONNECTION_RETRIES = 20
LOGGER = logging.getLogger('wcs.samlauth')
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('\n%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
LOGGER.addHandler(handler)


class BaseDockerServiceLayer(Layer):

    image_name = None
    container_name = None
    port = None
    name = None
    env = None
    retry = 1

    def __init__(self, bases=None, name=None, module=None):
        super().__init__(bases, self.name, module)
        self.external_service = None
        self.retry = 3

    def setUp(self):
        super().setUp()

        try:
            if self._test_connect_service():
                # Service is already running
                self.external_service = True
                return
        except Exception:
            self.external_service = False

        if not shutil.which('docker'):
            raise RuntimeError('You need to have docker installed in order to run those tests')
        if not self.is_docker_container_available():
            self._create_docker_container()
        self.start_service()

    def tearDown(self):
        if not self.external_service:
            self.stop_service()

    def _run_docker_command(self, command):
        result = subprocess.run(
            command,
            capture_output=True,
            text=True)

        if result.stderr:
            raise RuntimeError(
                f'Command ended with an error: {result.stderr}'
            )
        return result

    def start_service(self):
        result = self._run_docker_command(
            ["docker", "start", self.container_name]
        )
        if result.returncode == 0:
            LOGGER.info(f'{self.name} started: {result.stdout}')

        self._wait_for_service()

    def stop_service(self):
        result = self._run_docker_command(
            ["docker", "stop", self.container_name]
        )
        if result.returncode == 0:
            LOGGER.info(f'{self.name} stopped: {result.stdout}')

    def _create_docker_container(self, *arguments):
        if not arguments:
            arguments = [
                "docker",
                "container",
                "create",
                "--name", self.container_name,
                "-p", self.port,

            ]
        if self.env:
            for key, value in self.env.items():
                arguments.extend(['-e', f'{key}={value}'])
        arguments.append(self.image_name)

        if self.command:
            arguments.append(self.command)
        result = self._run_docker_command(arguments)
        LOGGER.info(f'Created {self.name} container: {self.container_name} ({result.stdout})')

    def is_docker_container_available(self):
        result = self._run_docker_command(
            ["docker", "ps", "-q", "-a", "-f", f"name={self.container_name}"],
        )
        if result.stderr:
            raise RuntimeError(
                f'Cannot determine if reistest image is available: {result.stderr}'
            )
        LOGGER.info(f'{self.name} container available at: {result.stdout}')
        return bool(result.stdout) and result.returncode == 0

    def _wait_for_service(self):
        raise NotImplementedError()

    def _test_connect_service(self):
        raise NotImplementedError()


class KeyCloakLayer(BaseDockerServiceLayer):
    name = "Keycloak service"
    container_name = 'keycloak_test'
    image_name = 'quay.io/keycloak/keycloak:24.0.2'
    port = '8000:8080'
    env = {
        'KEYCLOAK_ADMIN': 'admin',
        'KEYCLOAK_ADMIN_PASSWORD': 'admin',
        'KC_HEALTH_ENABLED': 'true',
        'KC_METRICS_ENABLED': 'true'
    }
    command = 'start-dev'
    admin_session = None

    def setUp(self):
        super().setUp()
        self.admin_session = requests.Session()
        self.admin_session.headers.update({'Content-Type': 'application/x-www-form-urlencoded'})
        self._configure()
        self._create_realm()

    def testSetUp(self):
        super().testSetUp()
        self['create_realm'] = self._create_realm
        self['delete_realm'] = self._delete_realm

    def testTearDown(self):
        super().testTearDown()
        del self["create_realm"]
        del self["delete_realm"]

    def tearDown(self):
        self._delete_realm()
        super().tearDown()

    def _configure(self):
        # Import realm
        access_token = requests.post(
            'http://localhost:8000/realms/master/protocol/openid-connect/token',
            data={'username': 'admin',
                  'password': 'admin',
                  'grant_type': 'password',
                  'client_id': 'admin-cli'}
        ).json()['access_token']

        self.admin_session.headers.update({'Authorization': f'Bearer {access_token}'})

    def _create_realm(self, filename='saml-test-realm.json'):
        self.admin_session.headers.update({'Content-Type': 'application/json'})

        response = self.admin_session.get(
            'http://localhost:8000/admin/realms/saml-test'
        )
        if response.status_code == 200:
            self._delete_realm()

        filename = os.path.join(os.path.dirname(__file__), 'tests', 'assets', filename)
        realm_data = None
        with open(filename, "rb") as f:
            realm_data = f.read()
            port = os.environ.get('WSGI_SERVER_PORT', '65035')
            realm_data_str = realm_data.decode('utf-8')
            realm_data_str.replace('http://localhost:8080/plone', f'http://localhost:{port}/plone')
            realm_data = realm_data_str.encode('utf-8')

        response = self.admin_session.post(
            'http://localhost:8000/admin/realms',
            data=realm_data
        )
        assert response.status_code == 201, 'Realm not created'

    def _delete_realm(self):
        self.admin_session.headers.update({'Content-Type': 'application/json'})
        response = self.admin_session.delete(
            'http://localhost:8000/admin/realms/saml-test'
        )
        assert response.status_code == 204, 'Realm not deleted'

    def _wait_for_service(self):
        counter = 0
        while not self._test_connect_service():
            if counter == MAX_CONNECTION_RETRIES:
                raise Exception("Cannot connect to keycloak  service")
            time.sleep(1)
            counter += 1

    def _test_connect_service(self):
        try:
            response = requests.get('http://localhost:8000/health/ready')
            return response.status_code == 200 and response.json()['status'] == 'UP'
        except requests.exceptions.ConnectionError:
            return False


KEYCLOAK_FIXTURE = KeyCloakLayer()


class SAMLAuthLayer(PloneSandboxLayer):

    defaultBases = (PLONE_FIXTURE, )

    def setUpZope(self, app, configurationContext):
        super().setUpZope(app, configurationContext)

        xmlconfig.string(
            '<configure xmlns="http://namespaces.zope.org/zope">'
            '  <include package="plone.autoinclude" file="meta.zcml" />'
            '  <autoIncludePlugins target="plone" />'
            '  <autoIncludePluginsOverrides target="plone" />'
            '</configure>',
            context=configurationContext)

        installProduct(app, 'wcs.samlauth')

    def setUpPloneSite(self, portal):
        super().setUpPloneSite(portal)
        #applyProfile(portal, 'wcs.samlauth:default')


SAMLAUTH_FIXTURE = SAMLAuthLayer()
SAMLAUTH_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(KEYCLOAK_FIXTURE, SAMLAUTH_FIXTURE, WSGI_SERVER_FIXTURE, ),
    name='SAMLAuth:Functional')

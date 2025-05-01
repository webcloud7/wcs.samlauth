# wcs.samlauth

wcs.samlauth is a saml authentication plugin based on python3-saml for plone 6.
It turns your plone site into a SP (Service Provider).
IDP (Identity Provider) is not supported.

The package is tested with plone 6.x and python 3.11/3.12. It does not officially support other versions.

## Goal

Make it as easy as possible to configure plone as a SP (Service Provider), without having a in depth knowledge of SAML and how it works under the hood. This package uses the high level API of python3-saml, which makes it easy to configure and use.


## TL;DR

1. Install wcs.samlauth plugin
2. Add PAS plugin via ZMI (in acl_users)
3. Go to http://localhost:8080/Plone/acl_users/saml/idp_metadata
4. Fetch or upload IDP metadata -> Click "Get and store metadata"
5. Go to http://localhost:8080/Plone/acl_users/saml/metadata and configure your IDP
6. Use http://localhost:8080/Plone/acl_users/saml/sls to login via IDP


## Architecure

The plugin is based on a similar architecture/concept as [pas.plugins.oidc](https://github.com/collective/pas.plugins.oidc/). It basically means that all endpoints are directly on the plugin.
The plugin does not override plones login/logout views. This is up to you.
If you only have one saml plugin it's possible to enable the **Challenge** plugin, which redirects to the saml login endpoint.

This enables you to add multiple saml plugins as well.

### Dependecies:

See [python3-saml](https://github.com/SAML-Toolkits/python3-saml)
Make especially sure the following packages can be installed, since the have some system dependencies as well:

- [xmlsec](https://pypi.org/project/xmlsec/)
- [lxml](https://pypi.org/project/lxml/)

For example, on a recent Ubuntu, you should run:
```shell
apt install pkg-config libxml2-dev libxmlsec1-dev libxmlsec1-openssl
```

## Endpoints


Given the ID of the SAML plugin is "saml":

- Expose SP metadata on http://localhost:8080/Plone/acl_users/saml/metadata
    - the SP metadata is partially generated and partially static. entityId, assertionConsumerService and singleLogoutService are generated
- SAML Login endpoint is http://localhost:8080/Plone/acl_users/saml/sls
- SAML ACS endpoint is http://localhost:8080/Plone/acl_users/saml/acs
- SAML Logout endpoint is http://localhost:8080/Plone/acl_users/saml/slo
- SAML SP initiated logout endpoint http://localhost:8080/Plone/acl_users/saml/logout
- Fetch IDP metadata http://localhost:8080/Plone/acl_users/saml/idp_metadata


## Features

- Fetch and store IDP metadata via IDP metadata endpoint
- Upload and store IDP metadata via file upload
- Multiple saml plugins at the same time
- Implements almost everything from python3-saml, this includes SP signing of the AuthnRequest and metadata
- Create a plone session and/or restapi token
- Enable/Disable the creation of a plone user
- Automatically updates user data (hardcoded, currently limited to email and fullname)
- Enable/Disable the validation of authn requests (Uses temporarly a `__saml` cookie)
- Prevent Redirect attacks, by validating the RelayState parameter and a and an "allowed" list of domains, where we can redirect to
- E2E tests with Keykloak as IDP in different configuration variations
- Manually tested with Azure AD as IDP
- Documentation use azure and keycloak as IDP
- Configure attribute mapping via ISAMLUserPropertiesMutator adapters.


## Installation


Add plugin to your buildout
```
[buildout]

...

eggs =
    wcs.samlauth
```


Add wcs.samlauth to plone docker image
```
$ docker run -p 8080:8080 -e SITE="mysite" -e ADDONS="wcs.samlauth" plone
```

From the ZMI go to `acl_users` and add the saml plugin.


## Development

It's best to use a local IDP, for example keycloak in order to make changes to this package.

Start a local keycloak server using docker:

```
$ docker run -p 8080:8080 -e KEYCLOAK_ADMIN=admin -e KEYCLOAK_ADMIN_PASSWORD=admin quay.io/keycloak/keycloak:22.0.2 start-dev

```

Install and run a test plone instance:

```
$ git clone git@github.com:webcloud7/wcs.samlauth.git && cd wcs.samlauth
$ make install
$ make run
```

## Custom attribute mapping

With version 1.1.0 wcs.samlauth now supports the mapping of custom saml attributes to plone user properties.

Example:
```
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
```

ZCML:
```
<adapter factory="PhoneUserPropertiesMutator"/>
```

A default adapter, which supports mapping email and fullname is registered by the plugin.
Any other attributes need to be implemented via custom adapters.

You can register multiple adapters and you can also override the values given
by the default adapter. Just make sure `_order` attribut on the adapter is higher than 1.



# Test

You need a local docker installation to run tests.

The package provides a docker test layer, which spins up keycloak and loads various configuration files into keycloak.


```
$ make test
```

Run individual tests:

```
$ ./bin/test -t test_whatever
```

# HowTo's

The tests/assets folder contains some keycloak configurations you can use for your test setup.
It inclues examples with SP signed autn requests and metadata.

The examples below do not use this specific saml feature which is required by most IDP.

## Manuall configuiration

You can configure everythin manully as well. Please see the [python3-saml documentation](https://github.com/SAML-Toolkits/python3-saml/blob/v1.15.0/README.md) for details

The configuration needs to be applied directly on the property tab of the saml plugin.


## Configure with keycloak as IDP

For both create a new saml pas plugin via ZMI in acl_users

### IDP part on keycloak

1. Login to your Keycloak admin console.

2. Create a new realm or use one that's already there. If not there create a test user.

3. With the data from http://localhost:8080/Plone/acl_users/saml/metadata create a new Client.

    Client type is SAML.

    Important note here: The client ID is identical to the SAML `EntityID`
    For example http://localhost:8080/keycloak/acl_users/saml/metadata

    ![Create keycloak client](./docs/images/keycloak_create_client.png?raw=true "Create keycloak client")

    Click "next"

4. Configure Home URL and Valid redirect URLs

    ![Configure keycloak](./docs/images/keycloak_config.png?raw=true "Configure keycloak")

    Click "Save"

5. Go to "Keys" tab and disable "Client signature required" 

    ![Disable signing](./docs/images/keycloak_disable.png?raw=true "Disable signing")

6. Configure attribute bindings

    Unter "Client scopes" click on URL which ends with /metadata-dedicated

    ![Disable signing](./docs/images/keycloak_scope.png?raw=true "Disable signing")

    Click on "Add predefined mapper"

    Chose the following mappers
    ![Disable signing](./docs/images/keycloak_attrs.png?raw=true "Disable signing")

    Click "Add"

7. Go to the Advance tab and configure the logout service redirect binding (python3-saml only supports the redirect binding here)

    ![Configure keycloak advanced](./docs/images/keycloak_advanced.png?raw=true "Configure keycloak advanced")

8. Copy the metadataa saml config URL

    ![copy url](./docs/images/keycloak_url.png?raw=true "copy url")

### SP part on your Plone site

1. Go to URL: http://localhost:8080/Plone/acl_users/saml/idp_metadata

    Enter the Url and Click on "Get and store metadata"

    ![copy url](./docs/images/plone_url.png?raw=true "copy url")    

    Hints: Keycloak has `authnRequestsSigned: true` hardcoded. 

**THATS IT!! Go To http://localhost:8080/Plone/acl_users/saml/sls to login via azure**

If this is the only saml plugin on your site and want all users to login via saml, then you can enable the Challenge Plugin and change the login and logout actions on your plone site to use the saml endpoints.


## Configure with Azure as IDP

This is a tutorial how to configure an azure cloud enterprise app as IDP for this plugin.

### IDP part on azure cloud

1. Go to your azure AD and create a new enterprise app.
    
    ![Create azure enterprise app](./docs/images/azure_create_app.png?raw=true "Create azure enterprise app")

2. Go to the "Single Sign on" section.

    ![SSO section](./docs/images/azure_sso.png?raw=true "SSO section")

3. Add SAML authentification to app.

    ![Add SAML](./docs/images/azure_saml.png?raw=true "Add SAML")

4. Gather the metadata from the SAML plugin.

    URL: http://localhost:8080/Plone/acl_users/saml/metadata

    ![Get metadata](./docs/images/plone_get_metadata.png?raw=true "Get metadata")

4. Manually edit "Basic SAML Configuration" (Info's can be taken from the SP metadata xml)

    Add EntityID and ACS. Optionally also add the Logout URL. Azure wants https there, so depending on your setup
    just leave it blank.

    ![Edit basic saml](./docs/images/azure_edit_basic.png?raw=true "Edit basic saml")

5. Edit "Attributes & Claims"
    
    The plugin only supports the email address, given name and surename
    You can configure more attributes, but they will be ignored.

    Important: The clame names need to be givenName, surename and email.
    Also remove the namespace and leave empty.
    
    ![Edit attrs](./docs/images/azure_attrs.png?raw=true "Edit attrs")

6. Download Federation metadata XML

    ![Download metadata](./docs/images/azure_download.png?raw=true "Download metadata")

### SP part on your Plone site

1. Go to URL: http://localhost:8080/Plone/acl_users/saml/idp_metadata

    Upload and store configuration from IDP (azure)

    ![Upload xml](./docs/images/plone_upload.png?raw=true "Upload xml")

2. The upload form also shows you what information has been gathered from the Metadata XML and what will be stored in your saml plugin

    ![Info xml](./docs/images/plone_info.png?raw=true "Info xml")

**THATS IT!! Go To http://localhost:8080/Plone/acl_users/saml/sls to login via azure**

If this is the only saml plugin on your site and want all users to login via saml, then you can enable the Challenge Plugin and change the login and logout actions on your plone site to use the saml endpoints.

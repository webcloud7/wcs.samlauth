Introduction
============

wcs.samlauth is a saml authentication plugin based on python3-saml.
I turns your plone site into a SP (Service Provider).
IDP (Identity Provider) is not supported, hence the name "samlauth".


Installation
============

::

    $ make install
    $ make run


We support both option since the makefile approach does not support yet all the features
from the zope2instance recipe. For example control scripts are not yet supported
But it's faster and more convenient to setup a docker test image


Test
====


::

    $ make test

Run individual tests:


::

    $ ./bin/test -t test_whatever

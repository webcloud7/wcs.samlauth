import os

from setuptools import setup

long_description = "\n\n".join(
    [
        open("README.md").read(),
        open(os.path.join("docs", "HISTORY.txt")).read(),
    ]
)

tests_require = [
    "plone.app.testing",
    "plone.testing",
    "plone.api",
    "zope.testrunner",
    "requests",
    "beautifulsoup4",
]

setup(
    name="wcs.samlauth",
    version="1.3.0",
    description="SAML authentication for plone sites",
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        "Environment :: Web Environment",
        "Framework :: Plone",
        "Framework :: Plone :: 6.0",
        "Framework :: Plone :: 6.1",
        "Framework :: Plone :: Addon",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Development Status :: 5 - Production/Stable",
    ],
    keywords="Plone Authentication SAML",
    author="Mathias Leimgruber",
    author_email="m.leimgruber@webcloud7.ch",
    url="https://pypi.python.org/pypi/wcs.samlauth",
    project_urls={
        "PyPI": "https://pypi.python.org/pypi/wcs.samlauth",
        "Source": "https://github.com/webcloud7/wcs.samlauth",
        "Tracker": "https://github.com/webcloud7/wcs.samlauth/issues",
        'Documentation': 'https://github.com/webcloud7/wcs.samlauth/blob/main/README.md',
    },
    license="GPL version 2",
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        "python3-saml",
        "Plone",
        "plone.autoinclude",
        "plone.restapi",
        "setuptools",
    ],
    extras_require=dict(
        test=tests_require,
        tests=tests_require,
    ),
    entry_points="""
    # -*- Entry points: -*-
    [plone.autoinclude.plugin]
    target = plone
    """,
)

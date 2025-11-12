from onelogin.saml2.idp_metadata_parser import OneLogin_Saml2_IdPMetadataParser
from plone.namedfile.field import NamedFile
from plone.z3cform.layout import wrap_form
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.statusmessages.interfaces import IStatusMessage
from wcs.samlauth import _
from z3c.form import button
from z3c.form import field
from z3c.form import form
from z3c.form.interfaces import WidgetActionExecutionError
from zope import schema
from zope.interface import Interface
from zope.interface import Invalid
from zope.interface import invariant
from zope.schema.interfaces import InvalidURI
import json


def valid_url(value):
    """Check for valid url, but don't break on umlauts
    """
    uri_field = schema.URI()

    try:
        return uri_field._validate(value) is None
    except InvalidURI:
        raise Invalid(_(u"Please enter a valid URL."))
    return False


class ILoadIdpMetadataSchema(Interface):

    metadata_url = schema.TextLine(
        title=_('label_metadata_url', default='IDP Metadata URL'),
        constraint=valid_url,
        required=False,
    )

    metadata_file = NamedFile(
        title=_('label_metadata_file', default='IDP Metadata File (XML)'),
        required=False,
    )

    @invariant
    def has_either_one(form):
        if not form.metadata_url and not form.metadata_file:
            raise Invalid("Provide a URL or a metadata xml")


class LoadIdPMetadataForm(form.Form):
    template = ViewPageTemplateFile('templates/load_idp_metadata_form.pt')
    label = _(u'label_load_idp_metadata_form', default=u'Load IDP Metadata')
    fields = field.Fields(ILoadIdpMetadataSchema)
    ignoreContext = True

    def __init__(self, *args, **kwargs):
        super(LoadIdPMetadataForm, self).__init__(*args, **kwargs)
        self.idp_data = None

    @button.buttonAndHandler(_(u'label_get_metadata', default=u'Get Metadata'), name='get')
    def get(self, action):
        data, errors = self.extractData()
        if errors:
            return

        if data['metadata_url']:
            self.idp_data = self._fetch_metadata(data['metadata_url'])
            msg = _('text_get', default=u'IDP Data has been fetched')
        elif data['metadata_file']:
            self.idp_data = self._parse_metadata(data['metadata_file'])
            msg = _('text_get', default=u'IDP Data has been uploaded')
        else:
            raise

        IStatusMessage(self.request).addStatusMessage(msg, type='info')

    @button.buttonAndHandler(_(u'label_get_and_metadata', default=u'Get and store metadata'), name='get_and_store')
    def get_and_store(self, action):
        data, errors = self.extractData()
        if errors:
            return

        if data['metadata_url']:
            self.idp_data = self._fetch_metadata(data['metadata_url'])
            msg = _(
                'text_get_and_store',
                default=u'IDP/SP Data has been fetched and stored in plugin settings.'
            )
        elif data['metadata_file']:
            self.idp_data = self._parse_metadata(data['metadata_file'])
            msg = _(
                'text_get_and_store',
                default=u'IDP/SP Data has been uploaded and stored in plugin settings.'
            )

        updated_data = self.context._update_metadata(self.idp_data)
        self.context.store(updated_data)

        IStatusMessage(self.request).addStatusMessage(msg, type='info')

    def formatted_idp_metadata(self):
        if self.idp_data:
            return json.dumps(self.idp_data, indent=4)

    def _fetch_metadata(self, url):
        """Fetch metadata from url and save it in plugin settings
        """
        plugin = self.context
        try:
            return plugin._fetch_metadata(url)
        except Exception as e:
            raise WidgetActionExecutionError(
                'metadata_url',
                Invalid(
                    _(u'error_metadata_fetch',
                      default=u'Error fetching metadata: ${error}',
                      mapping={'error': str(e)})
                )
            )

    def _parse_metadata(self, file_):
        return OneLogin_Saml2_IdPMetadataParser.parse(file_.data)


LoadIdPMetadataView = wrap_form(LoadIdPMetadataForm)

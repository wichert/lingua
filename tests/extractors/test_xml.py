# coding=utf-8
import mock
import pytest
from io import BytesIO
from lingua.extractors.xml import extract_xml

source = None


def _options(**kw):
    options = mock.Mock()
    options.domain = None
    options.keywords = []
    for (k, w) in kw.items():
        setattr(options, k, w)
    return options


@pytest.fixture
def fake_source(request):
    patcher = mock.patch('lingua.extractors.xml._open',
            side_effect=lambda *a: BytesIO(source))
    patcher.start()
    request.addfinalizer(patcher.stop)


@pytest.mark.usefixtures('fake_source')
def test_abort_on_syntax_error():
    global source
    source = b'''\xff\xff\xff'''
    with pytest.raises(SystemExit):
        list(extract_xml('filename', _options()))


@pytest.mark.usefixtures('fake_source')
def test_empty_xml():
    global source
    source = b'''<html/>'''
    assert list(extract_xml('filename', _options())) == []


@pytest.mark.usefixtures('fake_source')
def test_attributes_plain():
    global source
    source = u'''<html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy i18n:attributes="title" title="tést title"/>
                </html>
                '''.encode('utf-8')
    messages = list(extract_xml('filename', _options()))
    assert len(messages) == 1
    assert messages[0].msgid == u'tést title'


@pytest.mark.usefixtures('fake_source')
def test_custom_i18n_namespace():
    global source
    source = b'''<html i18n:domain="other">
                   <dummy i18n:translate="">Foo</dummy>
                   <other xmlns:i="http://xml.zope.org/namespaces/i18n"
                          i:domain="lingua">
                     <dummy i:translate="">Foo</dummy>
                   </other>
                   <dummy i18n:translate="">Foo</dummy>
                   <dummy i18n:translate="">Foo</dummy>
                 </html>
                 '''
    messages = list(extract_xml('filename', _options()))
    assert len(messages) == 4
    assert [m.msgid for m in messages] == [u'Foo'] * 4


@pytest.mark.usefixtures('fake_source')
def test_attributes_explicit_MessageId():
    global source
    source = u'''<html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                       i18n:domain="lingua">
                   <dummy i18n:attributes="title msg_title" title="test tïtle"/>
                 </html>
                  '''.encode('utf-8')
    messages = list(extract_xml('filename', _options()))
    assert len(messages) == 1
    assert messages[0].msgid == 'msg_title'
    assert messages[0].comment == u'Default: test tïtle'


@pytest.mark.usefixtures('fake_source')
def test_attributes_no_domain_without_domain_filter():
    global source
    source = b'''<html xmlns:i18n="http://xml.zope.org/namespaces/i18n">
                   <dummy i18n:attributes="title" title="test title"/>
                  </html>'''
    messages = list(extract_xml('filename', _options()))
    assert len(messages) == 1


@pytest.mark.usefixtures('fake_source')
def test_attributes_multiple_attributes():
    global source
    source = u'''<html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                       i18n:domain="lingua">
                   <dummy i18n:attributes="title ; alt" title="tést title"
                          alt="test ålt"/>
                 </html>'''.encode('utf-8')
    messages = list(extract_xml('filename', _options()))
    assert len(messages) == 2
    assert [m.msgid for m in messages] == [u'tést title', u'test ålt']


@pytest.mark.usefixtures('fake_source')
def test_attributes_multiple_attributes_explicit_msgid():
    global source
    source = u'''<html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy i18n:attributes="title msg_title; alt msg_alt"
                         title="test titlé" alt="test ålt"/>
                </html>'''.encode('utf-8')
    messages = list(extract_xml('filename', _options()))
    assert len(messages) == 2
    assert messages[0].msgid == u'msg_title'
    assert messages[0].comment == u'Default: test titlé'
    assert messages[1].msgid == u'msg_alt'
    assert messages[1].comment == u'Default: test ålt'


@pytest.mark.usefixtures('fake_source')
def test_translate_minimal():
    global source
    source = u'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy i18n:translate="">Dummy téxt</dummy>
                </html>'''.encode('utf-8')
    messages = list(extract_xml('filename', _options()))
    assert len(messages) == 1
    assert messages[0].msgid == u'Dummy téxt'


@pytest.mark.usefixtures('fake_source')
def test_translate_explicit_msgid():
    global source
    source = u'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy i18n:translate="msgid_dummy">Dummy téxt</dummy>
                </html>'''.encode('utf-8')
    messages = list(extract_xml('filename', _options()))
    assert len(messages) == 1
    assert messages[0].msgid == u'msgid_dummy'
    assert messages[0].comment == u'Default: Dummy téxt'

@pytest.mark.usefixtures('fake_source')
def test_translate_subelement():
    global source
    source = u'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy i18n:translate="msgid_dummy">Dummy
                    <strong>text</strong> demø</dummy>
                </html>
                '''.encode('utf-8')
    messages = list(extract_xml('filename', _options()))
    assert len(messages) == 1
    assert messages[0].msgid == u'msgid_dummy'
    assert messages[0].comment == u'Default: Dummy <dynamic element> demø'

@pytest.mark.usefixtures('fake_source')
def test_translate_named_subelement():
    global source
    source = u'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy i18n:translate="msgid_dummy">Dummy
                    <strong i18n:name="text">téxt</strong> demø</dummy>
                </html>
                '''.encode('utf-8')
    messages = list(extract_xml('filename', _options()))
    assert len(messages) == 1
    assert messages[0].msgid == u'msgid_dummy'
    assert messages[0].comment == u'Default: Dummy ${text} demø'


@pytest.mark.usefixtures('fake_source')
def test_translate_translated_subelement():
    global source
    source = u'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy i18n:translate="msgid_dummy">Dummy
                    <strong i18n:name="text"
                            i18n:translate="msgid_text">téxt</strong>
                    demø</dummy>
                </html>
                '''.encode('utf-8')
    messages = list(extract_xml('filename', _options()))
    assert len(messages) == 2
    assert messages[0].msgid == u'msgid_text'
    assert messages[0].comment == u'Default: téxt'
    assert messages[1].msgid == u'msgid_dummy'
    assert messages[1].comment == u'Default: Dummy ${text} demø'


@pytest.mark.usefixtures('fake_source')
def test_strip_extra_whitespace():
    global source
    source = b'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy i18n:translate="">Dummy


                  text</dummy>
                </html>
                '''
    messages = list(extract_xml('filename', _options()))
    assert messages[0].msgid == u'Dummy text'


@pytest.mark.usefixtures('fake_source')
def test_strip_trailing_and_leading_whitespace():
    global source
    source = b'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy i18n:translate="">
                    Dummy text
                  </dummy>
                </html>
                '''
    messages = list(extract_xml('filename', _options()))
    assert messages[0].msgid == u'Dummy text'


@pytest.mark.usefixtures('fake_source')
def test_html_entities():
    global source
    source = b'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <button i18n:translate="">Lock &amp; load&nbsp;</button>
                </html>
                '''
    messages = list(extract_xml('filename', _options()))
    assert messages[0].msgid == u'Lock &amp; load&nbsp;'


@pytest.mark.usefixtures('fake_source')
def test_ignore_undeclared_namespace():
    global source
    source = b'''\
                <html xmlns="http://www.w3.org/1999/xhtml"
                      xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <tal:block/>
                  <p i18n:translate="">Test</p>
                </html>
                '''
    messages = list(extract_xml('filename', _options()))
    assert messages[0].msgid == u'Test'


@pytest.mark.usefixtures('fake_source')
def test_ignore_dynamic_message():
    global source
    source = b'''\
                <html xmlns="http://www.w3.org/1999/xhtml"
                      xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <p i18n:translate="">${'dummy'}</p>
                </html>
                '''
    assert list(extract_xml('filename', _options())) == []


@pytest.mark.usefixtures('fake_source')
def test_translate_call_in_python_expression_attribute():
    global source
    source = b'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy tal:replace="_(u'foo')">Dummy</dummy>
                </html>
                '''
    messages = list(extract_xml('filename', _options()))
    assert messages[0].msgid == u'foo'


@pytest.mark.usefixtures('fake_source')
def test_translate_call_in_python_expression_in_char_data():
    global source
    source = b'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy>${_(u'foo')}</dummy>
                </html>
                '''
    messages = list(extract_xml('filename', _options()))
    assert messages[0].msgid == u'foo'


@pytest.mark.usefixtures('fake_source')
def test_translate_call_in_python_expression_in_attribute():
    global source
    source = b'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy title="${_(u'foo')}"></dummy>
                </html>
                '''
    messages = list(extract_xml('filename', _options()))
    assert messages[0].msgid == u'foo'


@pytest.mark.usefixtures('fake_source')
def test_multiple_expressions_with_translate_calls():
    global source
    source = b'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy title="${_(u'foo')} ${_(u'bar')}"></dummy>
                </html>
                '''
    messages = list(extract_xml('filename', _options()))
    assert messages[0].msgid == u'foo'
    assert messages[1].msgid == u'bar'


@pytest.mark.usefixtures('fake_source')
def test_translate_call_in_python_expression_in_attribute():
    global source
    source = b'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy title="${_(u'foo')}"></dummy>
                </html>
                '''
    messages = list(extract_xml('filename', _options()))
    assert messages[0].msgid == u'foo'

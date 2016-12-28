# coding=utf-8
try:
    from unittest import mock
except ImportError:
    import mock
import pytest
from io import BytesIO
from lingua.extractors.xml import ChameleonExtractor
from lingua.extractors.xml import get_python_expressions


xml_extractor = ChameleonExtractor()
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
        list(xml_extractor('filename', _options()))


@pytest.mark.usefixtures('fake_source')
def test_empty_xml():
    global source
    source = b'''<html/>'''
    assert list(xml_extractor('filename', _options())) == []


@pytest.mark.usefixtures('fake_source')
def test_attributes_plain():
    global source
    source = u'''<html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy i18n:attributes="title" title="tést title"/>
                </html>
                '''.encode('utf-8')
    messages = list(xml_extractor('filename', _options()))
    assert len(messages) == 1
    assert messages[0].msgid == u'tést title'
    assert messages[0].location[1] == 3


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
    messages = list(xml_extractor('filename', _options()))
    assert len(messages) == 4
    assert [m.msgid for m in messages] == [u'Foo'] * 4
    assert [m.location[1] for m in messages] == [2, 5, 7, 8]


@pytest.mark.usefixtures('fake_source')
def test_attributes_explicit_MessageId():
    global source
    source = u'''<html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                       i18n:domain="lingua">
                   <dummy i18n:attributes="title msg_title" title="test tïtle"/>
                 </html>
                  '''.encode('utf-8')
    messages = list(xml_extractor('filename', _options()))
    assert len(messages) == 1
    assert messages[0].msgid == 'msg_title'
    assert messages[0].comment == u'Default: test tïtle'
    assert messages[0].location[1] == 3


@pytest.mark.usefixtures('fake_source')
def test_attributes_no_domain_without_domain_filter():
    global source
    source = b'''<html xmlns:i18n="http://xml.zope.org/namespaces/i18n">
                   <dummy i18n:attributes="title" title="test title"/>
                  </html>'''
    messages = list(xml_extractor('filename', _options()))
    assert len(messages) == 1
    assert messages[0].location[1] == 2


@pytest.mark.usefixtures('fake_source')
def test_attributes_multiple_attributes():
    global source
    source = u'''<html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                       i18n:domain="lingua">
                   <dummy i18n:attributes="title ; alt" title="tést title"
                          alt="test ålt"/>
                 </html>'''.encode('utf-8')
    messages = list(xml_extractor('filename', _options()))
    assert len(messages) == 2
    assert [m.msgid for m in messages] == [u'tést title', u'test ålt']
    assert [m.location[1] for m in messages] == [3, 4]


@pytest.mark.usefixtures('fake_source')
def test_attributes_multiple_attributes_explicit_msgid():
    global source
    source = u'''<html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy i18n:attributes="title msg_title; alt msg_alt"
                         title="test titlé" alt="test ålt"/>
                </html>'''.encode('utf-8')
    messages = list(xml_extractor('filename', _options()))
    assert len(messages) == 2
    assert messages[0].msgid == u'msg_title'
    assert messages[0].comment == u'Default: test titlé'
    assert messages[1].msgid == u'msg_alt'
    assert messages[1].comment == u'Default: test ålt'
    assert [m.location[1] for m in messages] == [4, 4]


@pytest.mark.usefixtures('fake_source')
def test_translate_minimal():
    global source
    source = u'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy i18n:translate="">Dummy téxt</dummy>
                </html>'''.encode('utf-8')
    messages = list(xml_extractor('filename', _options()))
    assert len(messages) == 1
    assert messages[0].msgid == u'Dummy téxt'
    assert messages[0].location[1] == 3


@pytest.mark.usefixtures('fake_source')
def test_translate_explicit_msgid():
    global source
    source = u'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy i18n:translate="msgid_dummy">Dummy téxt</dummy>
                </html>'''.encode('utf-8')
    messages = list(xml_extractor('filename', _options()))
    assert len(messages) == 1
    assert messages[0].msgid == u'msgid_dummy'
    assert messages[0].comment == u'Default: Dummy téxt'
    assert messages[0].location[1] == 3


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
    messages = list(xml_extractor('filename', _options()))
    assert len(messages) == 1
    assert messages[0].msgid == u'msgid_dummy'
    assert messages[0].comment == u'Default: Dummy <dynamic element> demø'
    assert messages[0].location[1] == 3


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
    messages = list(xml_extractor('filename', _options()))
    assert len(messages) == 1
    assert messages[0].msgid == u'msgid_dummy'
    assert messages[0].comment == u'Default: Dummy ${text} demø'
    assert messages[0].location[1] == 3


@pytest.mark.usefixtures('fake_source')
def test_translate_translated_subelement():
    global source
    source = u'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy i18n:translate="">Dummy
                    <strong i18n:name="text"
                            i18n:translate="">téxt</strong>
                    demø</dummy>
                </html>
                '''.encode('utf-8')
    messages = list(xml_extractor('filename', _options()))
    assert len(messages) == 2
    assert messages[0].msgid == u'téxt'
    assert messages[0].comment == u'Used in sentence: "Dummy ${text} demø"'
    assert messages[0].location[1] == 5
    assert messages[1].msgid == u'Dummy ${text} demø'
    assert messages[1].comment == u'Canonical text for ${text} is: "téxt"'
    assert messages[1].location[1] == 3


@pytest.mark.usefixtures('fake_source')
def test_translate_translated_subelement_with_id():
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
    messages = list(xml_extractor('filename', _options()))
    assert len(messages) == 2
    assert messages[0].msgid == u'msgid_text'
    assert messages[0].comment == u'Default: téxt\nUsed in sentence: "Dummy ${text} demø"'
    assert messages[0].location[1] == 5
    assert messages[1].msgid == u'msgid_dummy'
    assert messages[1].comment == u'Default: Dummy ${text} demø\n' \
                                  u'Canonical text for ${text} is: "téxt"'
    assert messages[1].location[1] == 3


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
    messages = list(xml_extractor('filename', _options()))
    assert messages[0].msgid == u'Dummy text'
    assert messages[0].location[1] == 3


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
    messages = list(xml_extractor('filename', _options()))
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
    messages = list(xml_extractor('filename', _options()))
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
    messages = list(xml_extractor('filename', _options()))
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
    assert list(xml_extractor('filename', _options())) == []


@pytest.mark.usefixtures('fake_source')
def test_translate_call_in_python_expression_attribute():
    global source
    source = b'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy tal:replace="_(u'foo')">Dummy</dummy>
                </html>
                '''
    messages = list(xml_extractor('filename', _options()))
    assert messages[0].msgid == u'foo'


@pytest.mark.usefixtures('fake_source')
def test_translate_call_in_python_expression_repeat_attribute():
    global source
    source = b'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy tal:repeat="label _(u'foo')">${label}</dummy>
                </html>
                '''
    messages = list(xml_extractor('filename', _options()))
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
    messages = list(xml_extractor('filename', _options()))
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
    messages = list(xml_extractor('filename', _options()))
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
    messages = list(xml_extractor('filename', _options()))
    assert messages[0].msgid == u'foo'
    assert messages[1].msgid == u'bar'


@pytest.mark.usefixtures('fake_source')
def test_translate_multiple_defines():
    global source
    source = b'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <tal:analytics define="isAnon _('one'); account _('two')">
                  </tal:analytics>
                </html>
                '''
    messages = list(xml_extractor('filename', _options()))
    assert len(messages) == 2
    assert messages[0].msgid == u'one'
    assert messages[1].msgid == u'two'


@pytest.mark.usefixtures('fake_source')
def test_translate_explicit_python_expression_engine():
    global source
    source = b'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <tal:analytics define="layout python:_('one'); account _('two')">
                  </tal:analytics>
                </html>
                '''
    messages = list(xml_extractor('filename', _options()))
    assert len(messages) == 2
    assert messages[0].msgid == u'one'
    assert messages[1].msgid == u'two'


@pytest.mark.usefixtures('fake_source')
def test_translate_ignore_other_expression_engine():
    global source
    source = b'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <tal:analytics define="layout load:layout.pt; account _('two')">
                  </tal:analytics>
                </html>
                '''
    messages = list(xml_extractor('filename', _options()))
    assert len(messages) == 1
    assert messages[0].msgid == u'two'


@pytest.mark.usefixtures('fake_source')
def test_translate_ignore_other_content_expression_engine_with_structure():
    global source
    source = b'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <tal:var content="structure provider:my.content.provider">
                  </tal:var>
                </html>
                '''
    messages = list(xml_extractor('filename', _options()))
    assert len(messages) == 0


@pytest.mark.usefixtures('fake_source')
def test_translate_explicit_python_engine_with_structure():
    global source
    source = b'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <tal:var content="structure python:_('foo')">
                  </tal:var>
                </html>
                '''
    messages = list(xml_extractor('filename', _options()))
    assert len(messages) == 1
    assert messages[0].msgid == u'foo'


@pytest.mark.usefixtures('fake_source')
def test_translate_entities_in_python_expression():
    global source
    source = b'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <div class="${' disabled' if 1 &lt; 2 else None}"/>
                </html>
                '''
    list(xml_extractor('filename', _options()))


@pytest.mark.usefixtures('fake_source')
def test_curly_brace_in_python_expression():
    global source
    source = b'''\
            <html>
              <p>${request.route_url('set_locale', _query={'locale': 'de'})}</p>
            </html>
            '''
    list(xml_extractor('filename', _options()))


@pytest.mark.usefixtures('fake_source')
def test_curly_brace_in_python_attribute_expression():
    global source
    source = b'''\
            <html>
              <a href="${request.route_url('set_locale', _query={'locale': 'de'})}"></a>
            </html>
            '''
    list(xml_extractor('filename', _options()))


@pytest.mark.usefixtures('fake_source')
def test_curly_brace_related_syntax_error():
    global source
    source = b'''\
            <html>
              <a href="${request.route_url('set_locale', _}"></a>
            </html>
            '''
    with pytest.raises(SystemExit):
        list(xml_extractor('filename', _options()))


class Test_get_python_expression(object):
    def test_no_expressions(self):
        assert list(get_python_expressions('no python here', 'python')) == []

    def test_single_expression(self):
        assert list(get_python_expressions('${some_python}', 'python')) == ['some_python']

    def test_two_expressions(self):
        assert list(get_python_expressions('${one} ${two}', 'python')) == ['one', 'two']

    def test_nested_braces(self):
        assert list(get_python_expressions(
            '''${resource_url(_query={'one': 'one'})}''', 'python')) == \
            ['''resource_url(_query={'one': 'one'})''']


@pytest.mark.usefixtures('fake_source')
def test_python_expression_in_tales_expressions():
    global source
    source = u'''
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy tal:define="css_class css_class|string:${field.widget.css_class};">Dummy</dummy>
                </html>
                '''.encode('utf-8')
    assert list(xml_extractor('filename', _options())) == []


@pytest.mark.usefixtures('fake_source')
def test_ignore_structure_in_replace():
    global source
    source = u'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy tal:replace="structure _(u'føo')">Dummy</dummy>
                </html>
                '''.encode('utf-8')
    messages = list(xml_extractor('filename', _options()))
    assert messages[0].msgid == u'føo'


@pytest.mark.usefixtures('fake_source')
def test_repeat_multiple_assignment():
    global source
    source = u'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy tal:repeat="(ix, item) [(1, _(u'føo'))]">Dummy</dummy>
                </html>
                '''.encode('utf-8')
    messages = list(xml_extractor('filename', _options()))
    assert messages[0].msgid == u'føo'


@pytest.mark.usefixtures('fake_source')
def test_carriage_return_in_define():
    global source
    source = u'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy tal:define="foo True or
                                     _(u'føo')">Dummy</dummy>
                </html>
                '''.encode('utf-8')
    messages = list(xml_extractor('filename', _options()))
    assert messages[0].msgid == u'føo'


@pytest.mark.usefixtures('fake_source')
def test_multiline_replace():
    global source
    source = u'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy tal:replace="True or
                                      _(u'føo')">Dummy</dummy>
                </html>
                '''.encode('utf-8')
    messages = list(xml_extractor('filename', _options()))
    assert messages[0].msgid == u'føo'


@pytest.mark.usefixtures('fake_source')
def test_multiline_replace_with_structure():
    global source
    source = u'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy tal:replace="structure True or
                                      _(u'føo')">Dummy</dummy>
                </html>
                '''.encode('utf-8')
    messages = list(xml_extractor('filename', _options()))
    assert messages[0].msgid == u'føo'


@pytest.mark.usefixtures('fake_source')
def test_spaces_around_tal_pipe_symbol():
    global source
    source = u'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <div tal:repeat="choice values | field.widget.values"/>
                </html>
                '''.encode('utf-8')
    list(xml_extractor('filename', _options()))


@pytest.mark.usefixtures('fake_source')
def test_empty_element():
    global source
    source = u'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <img title="message" i18n:attributes="title">
                  <p></p>
                </html>
                '''.encode('utf-8')
    messages = list(xml_extractor('filename', _options()))
    assert len(messages) == 1


@pytest.mark.usefixtures('fake_source')
def test_brace_in_python_expression():
    global source
    source = u'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <p>${some_method(_('abc'), {'a':'b'})}</p>
                </html>
                '''.encode('utf-8')
    messages = list(xml_extractor('filename', _options()))
    assert len(messages) == 1
    assert messages[0].msgid == u'abc'


@pytest.mark.usefixtures('fake_source')
def test_translation_context():
    global source
    source = u'''<html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <button i18n:context="form" i18n:translate="">Save</button>
                </html>
                '''.encode('utf-8')
    messages = list(xml_extractor('filename', _options()))
    assert messages[0].msgid == u'Save'
    assert messages[0].msgctxt == u'form'


@pytest.mark.usefixtures('fake_source')
def test_translation_comment():
    global source
    source = u'''<html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <button i18n:comment="Generic save button" i18n:translate="">Save</button>
                </html>
                '''.encode('utf-8')
    messages = list(xml_extractor('filename', _options()))
    assert messages[0].msgid == u'Save'
    assert messages[0].comment == u'Generic save button'


@pytest.mark.usefixtures('fake_source')
def test_translation_comment_for_attribute():
    global source
    source = u'''<html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <input i18n:comment="Placeholder text" i18n:attributes="placeholder" placeholder="Email address">
                </html>
                '''.encode('utf-8')
    messages = list(xml_extractor('filename', _options()))
    assert messages[0].msgid == u'Email address'
    assert messages[0].comment == u'Placeholder text'


@pytest.mark.usefixtures('fake_source')
def test_translation_comment_and_msgid():
    global source
    source = u'''<html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <button i18n:comment="Generic save button" i18n:translate="btn_save">Save</button>
                </html>
                '''.encode('utf-8')
    messages = list(xml_extractor('filename', _options()))
    assert messages[0].msgid == u'btn_save'
    assert messages[0].comment == u'Generic save button\nDefault: Save'


@pytest.mark.usefixtures('fake_source')
def test_inherit_translation_comment():
    global source
    source = u'''<html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <div i18n:comment="Form buttons">
                    <button i18n:translate="">Save</button>
                  </div>
                </html>
                '''.encode('utf-8')
    messages = list(xml_extractor('filename', _options()))
    assert messages[0].msgid == u'Save'
    assert messages[0].comment == u'Form buttons'


@pytest.mark.usefixtures('fake_source')
def test_linenumbers():
    global source
    source = u'''<!DOCTYPE html>
                 <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <span />
                  <span
                    />
                  <?python foo = 1 ?>
                  <div>
                    <dummy i18n:comment="Generic save button" i18n:translate="dummy1">Foo<</dummy>
                  </div>
                  <div
                    foo="bar">
                    <dummy i18n:comment="Generic save button"
                           i18n:translate="dummy2">Foo</dummy>
                  </div>
                  <?python
                      import bar
                      bar.ham()
                      ?>
                  <div foo="bar"
                    class="blubb">
                    <dummy i18n:comment="Generic
                                         save button"><span tal:omit-tag="" i18n:translate="dummy3">Foo</span></dummy>
                  </div>
                  <script>
                  // <![CDATA[

                    $(document).ready(function () {
                    });
                  // ]]>
                  </script>
                </html>

                <!--
                    comment
                -->
                <tal:macros
                    xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                    i18n:domain="lingua">
                        <!--
                            comment
                        -->
                        <metal:action define-macro="action">
                            <dummy i18n:comment="Generic
                                                 save button">
                                <span tal:omit-tag="" i18n:translate="dummy4">Foo</span> ${value}
                            </dummy>
                        </metal:action>
                </tal:macros>
                '''.encode('utf-8')
    messages = list(xml_extractor('filename', _options()))
    got = [(x.msgid, x.location[1]) for x in messages]
    assert got == [
        ('dummy1', 9),
        ('dummy2', 14),
        ('dummy3', 23),
        ('dummy4', 46)]


@pytest.mark.usefixtures('fake_source')
def test_domain_filter():
    global source
    source = u'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy i18n:translate="">Dummy téxt</dummy>
                </html>'''.encode('utf-8')
    messages = list(xml_extractor('filename', _options(domain='other')))
    assert len(messages) == 0


@pytest.mark.usefixtures('fake_source')
def test_domain_filter_for_attribute():
    global source
    source = u'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy title="Dummy text" i18n:attributes="title"></dummy>
                </html>'''.encode('utf-8')
    messages = list(xml_extractor('filename', _options(domain='other')))
    assert len(messages) == 0


@pytest.mark.usefixtures('fake_source')
def test_domain_filter_for_expression():
    global source
    source = u'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <dummy>${_(u'foo')}</dummy>
                </html>'''.encode('utf-8')
    messages = list(xml_extractor('filename', _options(domain='other')))
    assert len(messages) == 0


@pytest.mark.usefixtures('fake_source')
def test_context_for_attributes():
    global source
    source = u'''\
                <html xmlns:i18n="http://xml.zope.org/namespaces/i18n"
                      i18n:domain="lingua">
                  <span title="message" i18n:context="figure" i18n:attributes="title"></span>
                </html>
                '''.encode('utf-8')
    messages = list(xml_extractor('filename', _options()))
    assert len(messages) == 1
    assert messages[0].msgctxt == 'figure'

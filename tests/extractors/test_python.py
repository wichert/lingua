# coding=utf-8
import mock
import pytest
from lingua.extractors.python import PythonExtractor


python_extractor = PythonExtractor()
source = None


@pytest.fixture
def fake_source(request):
    patcher = mock.patch('lingua.extractors.python._read',
            side_effect=lambda *a: source)
    patcher.start()
    request.addfinalizer(patcher.stop)


@pytest.mark.usefixtures('fake_source')
def test_syntax_error():
    global source
    options = mock.Mock()
    options.keywords = []
    source = u'''def class xya _(u'føo')'''
    with pytest.raises(SystemExit):
        generator = python_extractor('filename', options)
        list(generator)


@pytest.mark.usefixtures('fake_source')
def test_multiline_string():
    global source
    options = mock.Mock()
    options.keywords = []
    source = u'''_(u'őne two '\n'three')'''
    messages = list(python_extractor('filename', options))
    assert len(messages) == 1
    assert messages[0].msgid == u'őne two three'


@pytest.mark.usefixtures('fake_source')
def test_plural():
    global source
    options = mock.Mock()
    options.keywords = []
    source = u'''ngettext(u'one côw', u'%d cows', 5)'''
    messages = list(python_extractor('filename', options))
    assert len(messages) == 1
    assert messages[0].msgid == u'one côw'
    assert messages[0].msgid_plural == u'%d cows'

# coding=utf-8
import mock
import pytest
from lingua.extractors.python import extract_python


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
    source = b'''def class xya _('foo')'''
    with pytest.raises(SystemExit):
        generator = extract_python('filename', options)
        list(generator)


@pytest.mark.usefixtures('fake_source')
def test_multiline_string():
    global source
    options = mock.Mock()
    options.keywords = []
    source = b'''_('one two '\n'three')'''
    messages = list(extract_python('filename', options))
    assert len(messages) == 1
    assert messages[0].msgid == 'one two three'


@pytest.mark.usefixtures('fake_source')
def test_plural():
    global source
    options = mock.Mock()
    options.keywords = []
    source = b'''ngettext('one cow', '%d cows', 5)'''
    messages = list(extract_python('filename', options))
    assert len(messages) == 1
    assert messages[0].msgid == 'one cow'
    assert messages[0].msgid_plural == '%d cows'

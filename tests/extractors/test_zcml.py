try:
    from unittest import mock
except ImportError:
    import mock
import pytest
from io import BytesIO
from lingua.extractors.zcml import ZCMLExtractor


zcml_extractor = ZCMLExtractor()
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
    patcher = mock.patch('lingua.extractors.zcml._open',
            side_effect=lambda *a: BytesIO(source))
    patcher.start()
    request.addfinalizer(patcher.stop)


@pytest.mark.usefixtures('fake_source')
def test_empty_zcml():
    global source
    source = b'''<configure/>'''
    assert list(zcml_extractor('filename', _options())) == []


@pytest.mark.usefixtures('fake_source')
def test_i18n_without_domain():
    global source
    source = b'''\
                <configure>
                  <dummy title="test title"/>
                </configure>
              '''
    assert list(zcml_extractor('filename', _options())) == []


@pytest.mark.usefixtures('fake_source')
def test_i18n_with_domain():
    global source
    source = b'''\
                <configure i18n_domain="lingua">
                  <dummy title="test title"/>
                </configure>
              '''
    messages = list(zcml_extractor('filename', _options()))
    assert len(messages) == 1
    assert messages[0].msgid == u'test title'


@pytest.mark.usefixtures('fake_source')
def test_multiple_messages():
    global source
    source = b'''\
                <configure i18n_domain="lingua">
                  <dummy title="test title 1"/>
                  <dummy title="test title 2"/>
                </configure>
              '''
    messages = list(zcml_extractor('filename', _options()))
    assert len(messages) == 2
    assert messages[0].msgid == u'test title 1'
    assert messages[1].msgid == u'test title 2'


@pytest.mark.usefixtures('fake_source')
def test_domain_nesting():
    global source
    source = b'''\
                <configure>
                  <configure i18n_domain="lingua">
                      <dummy title="test title 1"/>
                  </configure>
                  <dummy title="test title 2"/>
                </configure>
              '''
    messages = list(zcml_extractor('filename', _options()))
    assert len(messages) == 1
    assert messages[0].msgid == u'test title 1'


@pytest.mark.usefixtures('fake_source')
def test_abort_on_syntax_error():
    global source
    source = b'''<configure'''
    with pytest.raises(SystemExit):
        list(zcml_extractor('filename', _options()))

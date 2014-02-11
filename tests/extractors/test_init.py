from lingua.extractors import check_c_format


def test_basic_c_format():
    flags = []
    check_c_format('Hello, %s', flags)
    assert 'c-format' in flags


def test_accept_no_format_hint():
    flags = ['no-c-format']
    check_c_format('Hello, %s', flags)
    assert 'c-format' not in flags


def test_escaped_percent_sign():
    flags = []
    check_c_format('100%%', flags)
    assert 'c-format' not in flags


def test_strftime_is_not_c_format():
    flags = []
    check_c_format('%Y-%m-%d', flags)
    assert 'c-format' not in flags

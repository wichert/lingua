import collections
import os
import re


Message = collections.namedtuple('Message',
        'msgctxt msgid msgstr flags comment tcomment location')

EXTRACTORS = {}
EXTENSIONS = {}


def register_extractor(identifier, extensions):
    def wrapper(func):
        EXTRACTORS[identifier] = func
        for extension in extensions:
            EXTENSIONS[extension] = func
        return func
    return wrapper


def get_extractor(filename):
    ext = os.path.splitext(filename)[1]
    return EXTENSIONS.get(ext)


# Based on http://www.cplusplus.com/reference/cstdio/printf/
_C_FORMAT = re.compile(r'''
        %
        [+ #0-]?               # flags
        (\d+|\*)?              # width
        (\.(\d+|\*))?           # precision
        (hh?|ll?|j|z|t|L)?     # length
        [diuoxXfFeEgGaAcspn%]  # specifier
        ''', re.VERBOSE)


# Based on http://docs.python.org/2/library/string.html#format-string-syntax
_PYTHON_FORMAT = re.compile(r'''
        \{
            (([_a-z](\w*)(\.[_a-z]\w*|\[\d+\])?)|\w+)?  # fieldname
            (![rs])?  # conversion
            (:\.?[<>=^]?[+ -]?\w*,?(\.\w+)?[bcdeEfFgGnosxX%]?)?  # format_spec
        \}
        ''', re.IGNORECASE | re.VERBOSE)


def _create_checker(format, flag):
    def check(buf, flags):
        if 'no-%s' % flag in flags:
            return
        if format.search(buf) is not None:
            flags.append(flag)
    return check


check_c_format = _create_checker(_C_FORMAT, 'c-format')
check_python_format = _create_checker(_PYTHON_FORMAT, 'python-format')

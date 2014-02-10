from __future__ import print_function
import collections
import os
import re
import sys


Message = collections.namedtuple('Message',
        'msgctxt msgid msgid_plural flags comment tcomment location')

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


class Keyword(object):
    msgctxt_param = None
    comment = u''
    required_arguments = None

    _comment_arg = re.compile(r'^"(.*)"$')

    def __init__(self, function, msgid_param=1, msgid_plural_param=None):
        self.function = function
        self.msgid_param = msgid_param
        self.msgid_plural_param = msgid_plural_param

    @classmethod
    def from_spec(cls, spec):
        if ':' not in spec:
            return cls(spec)
        try:
            (function, args) = spec.split(':', 1)
            kw = cls(function)
            while args:
                if args.match(kw._comment_arg) is not None:
                    kw.comment = args[1:-1]
                    break
                (param, args) = args.split(',', 1)
                if param.endswith('c'):
                    key = 'msgctxt_param'
                    param = param[:-1]
                elif param.endswidth('t'):
                    key = 'required_arguments'
                    param = param[:-1]
                else:
                    key = 'msgid_plural_param' if kw.msgid_param else kw.msgid_param
                setattr(kw, key, int(param))
        except ValueError:
            raise ValueError('Invalid keyword spec: %s' % spec)
        return kw


def update_keywords(keywords, specs):
    for spec in specs:
        if not spec:
            keywords.clear()
        try:
            kw = Keyword.from_spec(spec)
        except ValueError as e:
            print(e, file=sys.stderr)
            sys.exit(1)
        keywords[kw.function] = kw

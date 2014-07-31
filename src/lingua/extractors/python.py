from __future__ import print_function
import ast
import sys
from . import Extractor
from . import Message
from . import check_c_format
from . import check_python_format
from . import Keyword
from . import update_keywords


KEYWORDS = {
        'gettext': Keyword('gettext'),
        'ugettext': Keyword('ugettext'),
        'dgettext': Keyword('dgettext', 2, domain_param=1),
        'ldgettext': Keyword('ldgettext', 2, domain_param=1),
        'ngettext': Keyword('ngettext', 1, 2),
        'lngettext': Keyword('ngettext', 1, 2),
        'ungettext': Keyword('ungettext', 1, 2),
        'dngettext': Keyword('dngettext', 2, 3, domain_param=1),
        'ldngettext': Keyword('dngettext', 2, 3, domain_param=1),
        'N_': Keyword('N_', 1),
        }


def parse_keyword(node, keyword):
    if keyword.required_arguments and len(node.args) != keyword.required_arguments:
        return None
    try:
        domain = node.args[keyword.domain_param - 1].s \
                if keyword.domain_param else None
        msgid = node.args[keyword.msgid_param - 1].s
        msgid_plural = node.args[keyword.msgid_plural_param - 1].s \
                if keyword.msgid_plural_param else None
        msgctxt = node.args[keyword.msgctxt_param - 1].s \
                if keyword.msgctxt_param else None
        comment = keyword.comment
    except IndexError:
        return None
    return (domain, msgctxt, msgid, msgid_plural, comment)


def parse_translationstring(node):
    if not node.args:
        return None

    msgid = None
    default = u''
    if isinstance(node.args[0], ast.Str):
        msgid = node.args[0].s
    if len(node.args) > 2 and isinstance(node.args[2], ast.Str):
        default = node.args[2].s
    for keyword in node.keywords:
        if not isinstance(keyword.value, ast.Str):
            continue
        if keyword.arg == 'msgid':
            msgid = keyword.value.s
        elif keyword.arg == 'default':
            default = keyword.value.s
    if not msgid:
        return None

    comment = u'Default: %s' % default if default else u''
    return (None, None, msgid, None, comment)


def _read(filename):
    """Injection point for tests."""
    return open(filename, 'rb').read()


def _extract_python(filename, source, options, firstline=0):
    update_keywords(KEYWORDS, options.keywords)
    try:
        tree = ast.parse(source, filename)
    except SyntaxError as e:
        print('Aborting due to parse error in %s[%d]: %s' %
                        (filename, firstline + e.lineno, e.text), file=sys.stderr)
        sys.exit(1)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name):
            continue
        msg = None
        if node.func.id in KEYWORDS:
            msg = parse_keyword(node, KEYWORDS[node.func.id])
        elif node.func.id == '_':
            msg = parse_translationstring(node)
        if msg is None:
            continue

        if options.domain is not None and msg[0] and msg[0] != options.domain:
            continue

        flags = []
        check_c_format(msg[2], flags)
        check_python_format(msg[2], flags)
        yield Message(msg[1], msg[2], msg[3], flags, msg[4], u'', (filename, node.lineno))


class PythonExtractor(Extractor):
    extensions = ['.py']

    def __call__(self, filename, options):
        return _extract_python(filename, _read(filename), options)

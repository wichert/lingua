import ast
from . import register_extractor
from . import Message
from . import check_c_format
from . import check_python_format
from . import Keyword
from . import update_keywords


KEYWORDS = {
        'gettext': Keyword('gettext'),
        'ugettext': Keyword('ugettext'),
        'dgettext': Keyword('dgettext', 2),
        'ngettext': Keyword('ngettext', 1, 2),
        'lngettext': Keyword('ngettext', 1, 2),
        'ungettext': Keyword('ungettext', 1, 2),
        'dngettext': Keyword('dngettext', 2, 3),
        'ldngettext': Keyword('dngettext', 2, 3),
        'N_': Keyword('N_', 1),
        }


def parse_keyword(node, keyword):
    if keyword.required_arguments and len(node.args) != keyword.required_arguments:
        return None
    try:
        msgid = node.args[keyword.msgid_param - 1].s
        msgid_plural = node.args[keyword.msgid_plural_param - 1].s \
                if keyword.msgid_plural_param else None
        msgctxt = node.args[keyword.msgctxt_param - 1].s \
                if keyword.msgctxt_param else None
        comment = keyword.comment
    except IndexError:
        return None
    return (msgctxt, msgid, msgid_plural, comment)


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
    return (None, msgid, None, comment)


@register_extractor('python', ['.py'])
def extract_python(filename, options):
    update_keywords(KEYWORDS, options.keywords)
    tree = ast.parse(open(filename, 'rb').read(), filename)
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

        flags = []
        check_c_format(msg[1], flags)
        check_python_format(msg[1], flags)
        yield Message(msg[0], msg[1], msg[2], flags, msg[3], u'', (filename, node.lineno))

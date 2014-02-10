import ast
from . import register_extractor
from . import Message


KEYWORDS = {
        '_',
        'gettext',
        'ngettext',
        'ugettext',
        'ungettext',
        'dgettext',
        'dngettext',
        'N_',
        'pgettext',
        }


@register_extractor('python', ['.py'])
def extract_python(filename, options):
    tree = ast.parse(open(filename, 'rb').read(), filename)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name):
            continue
        if node.func.id not in KEYWORDS:
            continue
        if node.args:
            msg_id = None
            msg_default = u''
            if isinstance(node.args[0], ast.Str):
                msg_id = node.args[0].s
            if len(node.args) > 2 and isinstance(node.args[2], ast.Str):
                msg_default = node.args[2].s
            for keyword in node.keywords:
                if not isinstance(keyword.value, ast.Str):
                    continue
                if keyword.arg == 'msgid':
                    msg_id = keyword.value.s
                elif keyword.arg == 'default':
                    msg_default = keyword.value.s
            if msg_id:
                comment = u'Default: %s' % msg_default if msg_default else u''
                yield Message(None, msg_id, u'', [], comment, u'', (filename, node.lineno))

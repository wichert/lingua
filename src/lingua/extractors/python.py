import ast
from . import register_extractor


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
    messages = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name):
            continue
        if node.func.id not in KEYWORDS:
            continue
        if node.args:
            msg_id = msg_default = None
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
                    msg_id = keyword.value.s
            if msg_id:
                comments = [u'Default: %s' % msg_default] if msg_default else []
                messages.append((node.lineno, node.func.id, msg_id, comments))
    return messages

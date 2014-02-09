import ast


def extract_python(fileobj, keywords, comment_tags, options):
    tree = ast.parse(fileobj.read(), fileobj.name)
    messages = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name):
            continue
        if node.func.id not in keywords:
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

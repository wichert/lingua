from __future__ import print_function
import ast
import sys
import tokenize
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
}


def parse_keyword(node, keyword, filename, firstline):
    if keyword.required_arguments and len(node.args) != keyword.required_arguments:
        return None

    def get_string(param, error_msg):
        if not param:
            return None
        arg = node.args[param - 1]
        if not isinstance(node.args[0], ast.Str):
            print('%s[%d]: %s' % (filename, firstline + arg.lineno, error_msg),
                    file=sys.stderr)
            raise IndexError()
        else:
            return arg.s

    try:
        domain = get_string(keyword.domain_param, 'Domain argument must be a string')
        msgid = get_string(keyword.msgid_param, 'Message argument must be a string')
        msgid_plural = get_string(keyword.msgid_plural_param, 'Plural message argument must be a string')
        msgctxt = get_string(keyword.msgctxt_param, 'Context argument must be a string')
        comment = keyword.comment
    except IndexError:
        return None
    return (domain, msgctxt, msgid, msgid_plural, comment)


def parse_translationstring(node):
    if not node.args:
        return None

    msgid = None
    context = None
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
        elif keyword.arg == 'context':
            context = keyword.value.s
    if not msgid:
        return None

    comment = u'Default: %s' % default if default else u''
    return (None, context, msgid, None, comment)


def _open(filename):
    """Injection point for tests."""
    return open(filename, 'rb')


def safe_eval(s):
    tree = ast.compile(s)
    return tree.body[0].value.s


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
            msg = parse_keyword(node, KEYWORDS[node.func.id], filename, firstline)
        elif node.func.id == '_':
            msg = parse_translationstring(node)
        if msg is None:
            continue

        if options.domain is not None and msg[0] and msg[0] != options.domain:
            continue

        flags = []
        check_c_format(msg[2], flags)
        check_python_format(msg[2], flags)
        yield Message(msg[1], msg[2], msg[3], flags, msg[4], u'', (filename, firstline + node.lineno))


DYNAMIC = []


class TokenStreamer(object):
    def __init__(self, readline):
        self.queue = tokenize.generate_tokens(readline)
        self.pushed = []
        self.complete = False

    def __iter__(self):
        return self

    def _transform(self, raw_token):
        (token_type, token, loc_start, loc_end, line) = raw_token
        return (token_type, token, line, self)

    def push(self, token):
        self.pushed.append(token)
        self.complete = False

    def peek(self):
        token = self.next()
        self.push(token)
        return token

    def next(self):
        if self.complete:
            raise StopIteration()
        if self.pushed:
            token = self.pushed.pop()
        else:
            token = self._transform(next(self.queue))
        if token[0] == tokenize.ENDMARKER:
            self.complete = True
        return token

    __next__ = next  # For Python 3 compatibility


class PythonParser(object):
    last_comment = (-2, None)
    comment_marker = 'I18N:'

    def __call__(self, token_stream):
        self.messages = []
        self.handler = self.state_skip
        for (token_type, token, location, line) in token_stream:
            self.process_token(token_type, token, location, token_stream)

    def process_token(self, token_type, token, location, token_stream):
        if token_type == tokenize.COMMENT:
            self.process_comment(token, location)
        elif token_type in [tokenize.INDENT, tokenize.DEDENT, tokenize.NEWLINE, tokenize.NL]:
            return
        else:
            self.handler(token_type, token, location, token_stream)

    def process_comment(self, token, location):
        token = token[1:].strip()  # Remove leading hash
        if token.startswith(self.comment_marker):
            comment = token[len(self.comment_marker):].strip()
            if self.last_command[0] == location[0]:
                comment = self.last_commend[1] + ' ' + comment
            self.last_comment = (location[0], comment)

    def state_skip(self, token_type, token, location, token_stream):
        """Ignore all input until we see one of our keywords.
        """
        if token_type == tokenize.NAME and token in KEYWORDS:
            self.handler = self.state_in_keyword
            self.keyword = KEYWORDS[token]

    def state_in_keyword(self, token_type, token, location, token_stream):
        """Check if the keyword is used in a proper function call."""
        if token_type == tokenize.OP and token == '(':
            self.arguments = []
            self.argument_name = None
            self.in_argument = False
            self.handler = self.state_in_keyword_call
        else:
            self.handler = self.state_skip

    def state_in_keyword_call(self, token_type, token, location, token_stream):
        """Collect all keyword parameters."""
        if token_type == tokenize.OP:
            if token == ')':
                self.process_keyword()
                self.handler = self.state_skip
            elif token == ',':
                if not self.in_argument:
                    raise SyntaxError('Unexpected )')
                self.in_argument = False
            elif token == '(':  # Tuple
                self.in_argument = True
                self.skip_iterable('(', ')', token_stream)
                self.add_argument(DYNAMIC)
            elif token == '{':  # Dictionary
                self.in_argument = True
                self.skip_iterable('{', '}', token_stream)
                self.add_argument(DYNAMIC)
            elif token == '[':  # Array
                self.in_argument = True
                self.skip_iterable('[', ']', token_stream)
                self.add_argument(DYNAMIC)
            else:
                raise SyntaxError('Unepextected token: %s' % token)
        elif token_type == tokenize.STRING:
            if self.in_argument:
                token = safe_eval(token)
                self.arguments[-1] = (self.arguments[-1][0], self.arguments[-1][1] + token)
            else:
                token = safe_eval(token)
                self.add_argument(token)
                self.in_argument = True
        elif token_type == tokenize.NUMBER:
            if self.in_argument:
                raise SyntaxError('Unexpected number: %s' % token)
            self.add_argument(safe_eval(token))
        elif token_type == tokenize.NAME:
            self.in_argument = True
            (next_token_type, next_token) = token_stream.peek()[:2]
            if next_token_type == tokenize.OP and next_token in ',)':
                # Variable reference
                self.add_argument(DYNAMIC)
            elif next_token_type == tokenize.OP and next_token == '(':
                # Function call
                self.skip_iterable('(', ')', token_stream)
                self.add_argument(DYNAMIC)
            elif next_token_type == tokenize.OP and next_token == '=':
                if self.argument_name is not None:
                    raise SyntaxError('Unexpected token: %s' % token)
                next(token_stream)  # Pop the equal token
                self.argument_name = token
        else:
            raise SyntaxError('Unexpected token: %s' % token)
        # XXX Does this handle trailing comma: func(foo,x bar,)

    def add_argument(self, value):
        self.arguments.append((self.argument_name, value))
        self.argument_name = None

    def skip_iterable(self, start_token, end_token, token_stream):
        depth = 1
        for (token_type, token, loc_start, loc_end, line) in token_stream:
            if token_type == tokenize.OP:
                if token == start_token:
                    depth += 1
                elif token == end_token:
                    depth -= 1
                    if depth == 0:
                        return
            elif token_type == tokenize.ENDMARKER:
                raise SyntaxError('Unexpected end of file')
            elif token_type == tokenize.DEDENT:
                raise SyntaxError('Unexpected dedent')

    def process_keyword(self):
        print('Got a keyword: %s %r' % (self.keyword, self.arguments))


class PythonExtractor(Extractor):
    """Python sources"""
    extensions = ['.py']

    def __call__(self, filename, options, fileobj=None, lineno=0):
        if fileobj is None:
            fileobj = _open(filename)
        token_stream = TokenStreamer(fileobj.readline)
        parser = PythonParser()
        parser(token_stream)
        fileobj.seek(0)
        return _extract_python(filename, fileobj.read(), options, lineno)

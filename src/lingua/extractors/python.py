from __future__ import print_function
import ast
import io
import sys
import tokenize
import warnings
from . import Extractor
from . import Message
from . import check_comment_flags
from . import check_c_format
from . import check_python_format
from . import Keyword
from . import update_keywords


try:
    basestring
except NameError:
    basestring = str


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
    'pgettext': Keyword('pgettext', 2, msgctxt_param=1),
}


class ParseError(ValueError):
    def __init__(self, msg, lineno):
        self.lineno = lineno
        ValueError.__init__(self, msg)


def parse_keyword(arguments, keyword, filename, firstline):
    # This assumes kw arguments are not used.
    if keyword.required_arguments and len(arguments) != keyword.required_arguments:
        return None

    def get_string(param, error_msg):
        if not param:
            return None
        (arg_name, arg_value, lineno) = arguments[param - 1]
        if not isinstance(arg_value, basestring):
            print('%s[%d]: %s' % (filename, firstline + lineno, error_msg),
                    file=sys.stderr)
            raise IndexError()
        else:
            return arg_value

    try:
        domain = get_string(keyword.domain_param, 'Domain argument must be a string')
        msgid = get_string(keyword.msgid_param, 'Message argument must be a string')
        msgid_plural = get_string(keyword.msgid_plural_param, 'Plural message argument must be a string')
        msgctxt = get_string(keyword.msgctxt_param, 'Context argument must be a string')
        comment = keyword.comment
    except IndexError:
        return None
    return (domain, msgctxt, msgid, msgid_plural, comment)


def parse_translationstring(arguments, filename, firstline):
    if not arguments:
        return None

    msgid = None
    context = None
    default = u''
    args = [a[1] for a in arguments if a[0] is None]
    kwargs = dict((a[0], a[1]) for a in arguments if a[0] is not None)

    if isinstance(args[0], basestring):
        msgid = args[0]
    if len(args) > 2 and isinstance(args[2], basestring):
        default = args[2]
    for (key, value) in kwargs.items():
        if not isinstance(value, basestring):
            continue
        if key == 'msgid':
            msgid = value
        elif key == 'default':
            default = value
        elif key == 'context':
            context = value
    if not msgid:
        return None

    comment = u'Default: %s' % default if default else u''
    return (None, context, msgid, None, comment)


def _open(filename):
    """Injection point for tests."""
    return open(filename, 'r')


def safe_eval(s):
    if isinstance(s, bytes):
        s = s.decode('utf-8')
    return ast.literal_eval(s)


DYNAMIC = []


class _SafeReadline(object):
    def __init__(self, readline):
        self.readline = readline

    def __call__(self):
        line = self.readline()
        if isinstance(line, bytes):
            warnings.warn(
                'Python extractor called with bytes input. '
                'Please update your plugin to submit unicode instead.',
                UnicodeWarning, stacklevel=6)
            line = line.decode('utf-8')
        return line


class TokenStreamer(object):
    def __init__(self, readline):
        self.queue = tokenize.generate_tokens(_SafeReadline(readline))
        self.pushed = []
        self.complete = False

    def __iter__(self):
        return self

    def _transform(self, raw_token):
        (token_type, token, loc_start, loc_end, line) = raw_token
        return (token_type, token, loc_start, self)

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

    def __call__(self, token_stream, options, filename, firstline):
        self.options = options
        if options.comment_tag is True:
            self.include_comments = 'all'
        elif options.comment_tag is None:
            self.include_comments = 'none'
        else:
            self.include_comments = 'tagged'
            self.comment_marker = options.comment_tag
        self.comment_tag = options.comment_tag
        self.filename = filename
        self.firstline = firstline
        self.messages = []
        self.handler = self.state_skip
        try:
            for (token_type, token, location, _) in token_stream:
                self.process_token(token_type, token, location, token_stream)
        except tokenize.TokenError as e:
            print('Aborting due to parse error in %s[%d]: %s' %
                    (filename, firstline + e.args[1][0], e.args[0]),
                    file=sys.stderr)
            sys.exit(1)
        except ParseError as e:
            print('Aborting due to parse error in %s[%d]: %s' %
                    (filename, firstline + e.lineno, e.args[0]),
                    file=sys.stderr)
            sys.exit(1)
        return self.messages

    def process_token(self, token_type, token, location, token_stream):
        if token_type == tokenize.COMMENT:
            self.process_comment(token, location)
        elif token_type in [tokenize.INDENT, tokenize.DEDENT, tokenize.NEWLINE, tokenize.NL]:
            return
        else:
            self.handler(token_type, token, location, token_stream)

    def process_comment(self, token, location):
        if self.include_comments == 'none':
            return
        comment = token[1:].strip()  # Remove leading hash
        if self.include_comments == 'all' or comment.startswith(self.comment_marker):
            if self.include_comments == 'tagged':
                comment = comment[len(self.comment_marker):].strip()
            (flags, comment) = check_comment_flags(comment)
            if self.messages and self.messages[-1].location[1] == (self.firstline + location[0]):
                last_message = self.messages[-1]
                # Comment at the end of the line of a keyword call
                new_comment = []
                if self.messages[-1].comment:
                    new_comment.append(last_message.comment)
                new_comment.append(comment)
                self.messages[-1] = Message(last_message.msgctxt, last_message.msgid,
                    last_message.msgid_plural, last_message.flags, '\n'.join(new_comment),
                    last_message.tcomment, last_message.location)
            else:
                if self.last_comment[0] == location[0] - 1:
                    comment = self.last_comment[1] + ' ' + comment
                    flags = self.last_comment[2] + self.last_comment[2]
                self.last_comment = (location[0], comment, flags)

    def state_skip(self, token_type, token, location, token_stream):
        """Ignore all input until we see one of our keywords.
        """
        if token_type == tokenize.NAME and (token in KEYWORDS or token == '_'):
            self.handler = self.state_in_keyword
            self.keyword = KEYWORDS.get(token, None)
            self.lineno = location[0]

    def state_in_keyword(self, token_type, token, location, token_stream):
        """Check if the keyword is used in a proper function call."""
        if token_type == tokenize.OP and token == '(':
            self.arguments = []
            self.argument_name = None
            self.in_argument = False
            self.in_string = False
            self.handler = self.state_in_keyword_call
        else:
            self.handler = self.state_skip

    def state_in_keyword_call(self, token_type, token, location, token_stream):
        """Collect all keyword parameters."""
        if token_type != tokenize.STRING:
            self.in_string = False
        if token_type == tokenize.OP:
            if token == ')':
                self.process_keyword()
                self.handler = self.state_skip
            elif token == ',':
                if not self.in_argument:
                    raise ParseError('Unexpected )', location[0])
                self.in_argument = False
            elif token == '(':  # Tuple
                self.in_argument = True
                self.skip_iterable('(', ')', token_stream)
                self.add_argument(DYNAMIC, location[0])
            elif token == '{':  # Dictionary
                self.in_argument = True
                self.skip_iterable('{', '}', token_stream)
                self.add_argument(DYNAMIC, location[0])
            elif token == '[':  # Array
                self.in_argument = True
                self.skip_iterable('[', ']', token_stream)
                self.add_argument(DYNAMIC, location[0])
            elif token == '.':
                pass
            else:
                raise ParseError('Unexpected token: %s' % token, location[0])
        elif token_type == tokenize.STRING:
            if self.in_string:
                token = safe_eval(token)
                self.arguments[-1] = (self.arguments[-1][0], self.arguments[-1][1] + token, self.arguments[-1][2])
            else:
                token = safe_eval(token)
                self.add_argument(token, location[0])
                self.in_argument = True
                self.in_string = True
        elif token_type == tokenize.NUMBER:
            if self.in_argument:
                raise ParseError('Unexpected number: %s' % token, location[0])
            self.add_argument(safe_eval(token), location[0])
        elif token_type == tokenize.NAME:
            self.in_argument = True
            (next_token_type, next_token) = token_stream.peek()[:2]
            if next_token_type == tokenize.OP and next_token in ',)':
                # Variable reference
                self.add_argument(DYNAMIC, location[0])
            elif next_token_type == tokenize.OP and next_token == '(':
                # Function call
                next(token_stream)  # Make sure skip_iterable does not see ( again
                self.skip_iterable('(', ')', token_stream)
                self.add_argument(DYNAMIC, location[0])
            elif next_token_type == tokenize.OP and next_token == '=':
                if self.argument_name is not None:
                    raise ParseError('Unexpected token: %s' % token, location[0])
                next(token_stream)  # Pop the equal token
                self.argument_name = token
        else:
            raise ParseError('Unexpected token: %s' % token, location[0])
        # XXX Does this handle trailing comma: func(foo,x bar,)

    def add_argument(self, value, lineno):
        self.arguments.append((self.argument_name, value, lineno))
        self.argument_name = None

    def skip_iterable(self, start_token, end_token, token_stream):
        depth = 1
        for (token_type, token, loc, _) in token_stream:
            if token_type == tokenize.OP:
                if token == start_token:
                    depth += 1
                elif token == end_token:
                    depth -= 1
                    if depth == 0:
                        return
            elif token_type == tokenize.ENDMARKER:
                raise ParseError('Unexpected end of file', loc[0])
            elif token_type == tokenize.DEDENT:
                raise ParseError('Unexpected dedent', loc[0])

    def process_keyword(self):
        if self.keyword is not None:
            msg = parse_keyword(self.arguments, self.keyword, self.filename, self.firstline)
        else:
            msg = parse_translationstring(self.arguments, self.filename, self.firstline)
        if msg is None:
            return

        if self.options.domain is not None and msg[0] and msg[0] != self.options.domain:
            return

        comments = []
        flags = []
        if msg[4]:
            comments.append(msg[4])
        if self.last_comment[0] == (self.lineno - 1):
            comments.append(self.last_comment[1])
            for f in self.last_comment[2]:
                if f not in flags:
                    flags.append(f)
        comment = u'\n'.join(comments)

        check_c_format(msg[2], flags)
        check_python_format(msg[2], flags)
        self.messages.append(Message(msg[1], msg[2], msg[3], flags, comment, u'', (self.filename, self.firstline + self.lineno)))


def _extract_python(filename, source, options, firstline=0):
    if isinstance(source, bytes):
        source = source.decode('utf-8')
    fileobj = io.StringIO(source)
    extractor = PythonExtractor()
    return extractor(filename, options, fileobj, firstline)


class PythonExtractor(Extractor):
    """Python sources"""
    extensions = ['.py']

    def __call__(self, filename, options, fileobj=None, lineno=0):
        update_keywords(KEYWORDS, options.keywords)
        if fileobj is None:
            fileobj = _open(filename)
        token_stream = TokenStreamer(fileobj.readline)
        parser = PythonParser()
        return parser(token_stream, options, filename, lineno)

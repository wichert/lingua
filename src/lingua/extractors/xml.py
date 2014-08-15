from __future__ import absolute_import
from __future__ import print_function
import ast
import collections
import re
import sys
from chameleon.namespaces import I18N_NS
from chameleon.namespaces import TAL_NS
from chameleon.program import ElementProgram
from chameleon.zpt.program import MacroProgram
from chameleon.tal import parse_defines
from chameleon.tales import split_parts
from chameleon.utils import decode_htmlentities

from .python import _extract_python
from . import Extractor
from . import Message


def _open(filename):
    """Injection point for tests."""
    return open(filename, 'rb')


ENGINE_PREFIX = re.compile(r'^\s*([a-z\-_]+):\s*')
STRUCTURE_PREFIX = re.compile(r'\s*(structure|text)\s+(.*)', re.DOTALL)
WHITESPACE = re.compile(u"\s+")
EXPRESSION = re.compile(u"\s*\${(.*?)}\s*")
UNDERSCORE_CALL = re.compile("_\(.*\)")


class TranslateContext(object):
    def __init__(self, domain, msgid, filename, lineno):
        self.domain = domain
        self.msgid = msgid
        self.text = []
        self.filename = filename
        self.lineno = lineno

    def add_text(self, text):
        self.text.append(text)

    def add_element(self, element):
        attributes = element['ns_attrs']
        name = attributes.get((I18N_NS, 'name'))
        if name:
            self.text.append(u'${%s}' % name)
        else:
            self.text.append(u'<dynamic element>')

    def ignore(self):
        text = u''.join(self.text).strip()
        text = WHITESPACE.sub(u' ', text)
        text = EXPRESSION.sub(u'', text)
        return not text

    def message(self):
        text = u''.join(self.text).strip()
        text = WHITESPACE.sub(u' ', text)
        if not self.msgid:
            self.msgid = text
            text = u''
        comment = u'Default: %s' % text if text else u''
        return Message(None, self.msgid, None, [], comment, u'',
                (self.filename, self.lineno))


class ChameleonExtractor(Extractor, ElementProgram):
    '''Chameleon templates (defaults to Python expressions)'''
    extensions = ['.pt']
    DEFAULT_NAMESPACES = MacroProgram.DEFAULT_NAMESPACES
    default_config = {
            'default-engine': 'python',
            }

    def __call__(self, filename, options):
        self.options = options
        self.filename = filename
        self.target_domain = options.domain
        self.messages = []
        self.domainstack = collections.deque([None])
        self.translatestack = collections.deque([None])
        self.linenumber = 1
        try:
            source = _open(filename).read().decode('utf-8')
        except UnicodeDecodeError as e:
            print('Aborting due to parse error in %s: %s' %
                    (self.filename, e), file=sys.stderr)
            sys.exit(1)
        ElementProgram.__init__(self, source, filename=filename)
        return self.messages

    def visit(self, kind, args):
        visitor = getattr(self, 'visit_%s' % kind, None)
        if visitor is not None:
            return visitor(*args)

    def visit_element(self, start, end, children):
        if self.translatestack and self.translatestack[-1]:
            self.translatestack[-1].add_element(start)

        attributes = start['ns_attrs']
        plain_attrs = dict((a['name'].split(':')[-1], a['value']) for a in start['attrs'])
        new_domain = attributes.get((I18N_NS, 'domain'))
        if new_domain:
            self.domainstack.append(new_domain)
        elif self.domainstack:
            self.domainstack.append(self.domainstack[-1])

        i18n_translate = attributes.get((I18N_NS, 'translate'))
        if i18n_translate is not None:
            self.translatestack.append(TranslateContext(
                self.domainstack[-1] if self.domainstack else None,
                i18n_translate, self.filename, self.linenumber))
        else:
            self.translatestack.append(None)

        if self.domainstack:
            i18n_attributes = attributes.get((I18N_NS, 'attributes'))
            if i18n_attributes:
                parts = [p.strip() for p in i18n_attributes.split(';')]
                for msgid in parts:
                    if ' ' not in msgid:
                        if msgid not in plain_attrs:
                            continue
                        self.add_message(plain_attrs[msgid])
                    else:
                        try:
                            (attr, msgid) = msgid.split()
                        except ValueError:
                            continue
                        if attr not in plain_attrs:
                            continue
                        self.add_message(msgid, u'Default: %s' % plain_attrs[attr])

            for (attribute, value) in attributes.items():
                value = decode_htmlentities(value)
                for source in self.get_code_for_attribute(attribute, value):
                    self.parse_python(source)

        for child in children:
            self.visit(*child)

        if self.domainstack:
            self.domainstack.pop()

        translate = self.translatestack.pop()
        if translate and not translate.ignore() and translate.domain and \
                (self.target_domain is None or translate.domain == self.target_domain):
            self.messages.append(translate.message())

    def visit_text(self, data):
        for line in data.splitlines():
            for source in EXPRESSION.findall(line):
                if UNDERSCORE_CALL.search(source):
                    self.parse_python(source)
            self.linenumber += 1
        if self.translatestack[-1]:
            self.translatestack[-1].add_text(data)

    def add_message(self, msgid, comment=u''):
        self.messages.append(Message(None, msgid, None, [], comment, u'',
            (self.filename, self.linenumber)))

    def _assert_valid_python(self, value):
        if not is_valid_python(value):
            print('Aborting due to Python syntax error in %s[%d]: %s' %
                    (self.filename, self.linenumber, value))
            sys.exit(1)

    def get_code_for_attribute(self, attribute, value):
        default_engine = self.config['default-engine']
        if attribute[0] == TAL_NS:
            if attribute[1] in ['content', 'replace']:
                for (engine, value) in split_expression(value, default_engine):
                    if engine == 'python':
                        m = STRUCTURE_PREFIX.match(value)
                        if m is not None:
                            value = m.group(2)
                        value = '(%s)' % value
                        self._assert_valid_python(value)
                        yield value
            if attribute[1] == 'define':
                for (scope, var, value) in parse_defines(value):
                    for (engine, value) in split_expression(value, default_engine):
                        if engine == 'python':
                            value = '(%s)' % value
                            self._assert_valid_python(value)
                            yield value
            elif attribute[1] == 'repeat':
                defines = parse_defines(value)
                if len(defines) != 1:
                    print('Aborting due to syntax error in %s[%d]: %s' % (
                            self.filename, self.linenumber, value))
                scope, var, value = defines[0]
                for (engine, value) in split_expression(value, default_engine):
                    if engine == 'python':
                        self._assert_valid_python(value)
                        yield value
        else:
            try:
                for source in get_python_expressions(value, default_engine):
                    yield source
            except SyntaxError:
                print('Aborting due to Python syntax error in %s[%d]: %s' %
                        (self.filename, self.linenumber, value))
                sys.exit(1)

    def parse_python(self, source):
        assert isinstance(source, type(u''))
        for message in _extract_python(self.filename, source, self.options, self.linenumber):
            self.messages.append(Message(*message[:6],
                location=(self.filename, self.linenumber + message.location[1])))


class ZopeExtractor(ChameleonExtractor):
    '''Zope templates (defaults to TALES expressions)'''
    extensions = ['.zpt', '.cpt']
    default_config = {
            'default-engine': 'tales',
            }


def is_valid_python(source):
    try:
        ast.parse(source, mode='eval')
    except SyntaxError:
        return False
    else:
        return True


def split_expression(source, default_engine):
    for part in split_parts.split(source):
        expression = part.strip().replace('\\|', '|')
        yield get_tales_engine(expression, default_engine)



def get_tales_engine(source, default_engine):
    m = ENGINE_PREFIX.match(source)
    if m is None:
        return (default_engine, source)
    else:
        return (m.group(1), source[m.end():])


def get_python_expressions(source, default_engine):
    regex = re.compile(r'(?<!\\)\$({(?P<expression>.*)})', re.DOTALL)
    while source:
        m = regex.search(source)
        if m is None:
            break

        source = source[m.start():]
        matched = m.group(0)

        # We foundsomething that looks like ${...}, but could also be
        # ${...}..}, so keep trying to parse while stripping the last
        # character until either all python validates, or we no longer
        # match

        m = regex.search(source)
        while m is not None:
            candidate = m.group('expression')
            candidates = [code for (engine, code) in split_expression(candidate, default_engine)
                          if engine == 'python']
            if all(is_valid_python(c) for c in candidates):
                # All valid, so return and move to next ${ block
                for c in candidates:
                    yield c
                source = source[m.end():]
                break
            else:
                # Syntax error somewhere, so try again with last character
                # stripped.
                matched = matched[:-1]
                m = regex.search(matched)

        if m is None:
            # We found ${, but could not find a valid python expression
            raise SyntaxError()

from __future__ import absolute_import
from __future__ import print_function
import ast
import collections
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
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
    def __init__(self, domain, msgctxt, msgid, comment, filename, lineno):
        self.domain = domain
        self.msgctxt = msgctxt
        self.msgid = msgid
        self.text = []
        self.filename = filename
        self.lineno = lineno
        self.parent = None
        self.children = OrderedDict()
        self.comment = comment

    def add_text(self, text):
        self.text.append(text)

    def add_element(self, element):
        attributes = element['ns_attrs']
        name = attributes.get((I18N_NS, 'name'))
        if name:
            self.text.append(u'${%s}' % name)
        else:
            self.text.append(u'<dynamic element>')

    def register_child(self, element, context):
        attributes = element['ns_attrs']
        name = attributes.get((I18N_NS, 'name'))
        if name:
            self.children[name] = context

    def ignore(self):
        text = u''.join(self.text).strip()
        text = WHITESPACE.sub(u' ', text)
        text = EXPRESSION.sub(u'', text)
        return not text

    def full_text(self):
        text = u''.join(self.text).strip()
        text = WHITESPACE.sub(u' ', text)
        return text

    def message(self):
        text = self.full_text()
        if not self.msgid:
            self.msgid = text
            text = u''
        comments = []
        if self.comment:
            comments.append(self.comment)
        if text:
            comments.append(u'Default: %s' % text)
        for (name, context) in self.children.items():
            comments.append(u'Canonical text for ${%s} is: "%s"' %
                    (name, context.full_text()))
        if self.parent:
            comments.append(u'Used in sentence: "%s"' %
                    self.parent.full_text())
        return Message(self.msgctxt, self.msgid, None, [],
                u'\n'.join(comments), u'',
                (self.filename, self.lineno))


def get_newline_count(s):
    s = s or ''
    return len(s.split('\n')) - 1


def get_plain_attrs(attrs):
    plain_attrs = dict()
    offset = 0
    for attr in attrs:
        offset += get_newline_count(attr['space'] + attr['name'] + attr['eq'] + attr['quote'])
        post_offset = offset + get_newline_count(attr['value'] + attr['quote'])
        plain_attrs[attr['name'].split(':')[-1]] = (attr['value'], offset, post_offset)
        offset = post_offset
    return plain_attrs


class ChameleonExtractor(Extractor, ElementProgram):
    '''Chameleon templates (defaults to Python expressions)'''
    extensions = ['.pt']
    DEFAULT_NAMESPACES = MacroProgram.DEFAULT_NAMESPACES
    default_config = {
        'default-engine': 'python',
    }

    def __call__(self, filename, options, fileobj=None, lineno=0):
        self.options = options
        self.filename = filename
        self.target_domain = options.domain
        self.messages = []
        self.domainstack = collections.deque([(None, None, None)])
        self.translatestack = collections.deque([None])
        self.linenumber = 1
        if fileobj is None:
            fileobj = _open(filename)
        try:
            source = fileobj.read().decode('utf-8')
            ElementProgram.__init__(self, source, filename=filename)
        except UnicodeDecodeError as e:
            print('Aborting due to parse error in %s: %s' %
                    (self.filename, e), file=sys.stderr)
            sys.exit(1)
        except KeyError as e:  # Chameleon attribute error
            print('Aborting due to parse error in %s: %s' %
                    (self.filename, e.message), file=sys.stderr)
            sys.exit(1)
        return [m.message() if isinstance(m, TranslateContext) else m
                for m in self.messages]

    def visit(self, kind, args):
        visitor = getattr(self, 'visit_%s' % kind, None)
        if visitor is not None:
            return visitor(*args)
        else:
            print("Warning: Unknown node type '%s' in %s, linenumbers might be off. Please report this warning." %
                    (kind, self.filename), file=sys.stderr)

    def visit_start_tag(self, element):
        self.visit_element(element, None, [])

    def visit_element(self, start, end, children):
        self.linenumber += get_newline_count(start['prefix'] + start['name'])
        if self.translatestack and self.translatestack[-1]:
            self.translatestack[-1].add_element(start)

        attributes = start['ns_attrs']
        plain_attrs = get_plain_attrs(start['attrs'])
        childs_lineno = self.linenumber
        post_offset = [x[2] for x in plain_attrs.values()]
        if post_offset:
            childs_lineno += max(post_offset)
        childs_lineno += get_newline_count(start['suffix'])
        new_domain = attributes.get((I18N_NS, 'domain'))
        old_domain = self.domainstack[-1][0] if self.domainstack else None
        new_context = attributes.get((I18N_NS, 'context'))
        old_context = self.domainstack[-1][1] if self.domainstack else None
        new_comment = attributes.get((I18N_NS, 'comment'))
        old_comment = self.domainstack[-1][2] if self.domainstack else None
        if new_domain or new_context or new_comment:
            self.domainstack.append((
                new_domain or old_domain,
                new_context or old_context,
                new_comment or old_comment))
        elif self.domainstack:
            self.domainstack.append(self.domainstack[-1])

        current_domain = self.domainstack[-1][0]
        include_domain = self.target_domain is None or self.target_domain == current_domain

        i18n_translate = attributes.get((I18N_NS, 'translate'))
        if i18n_translate is not None:
            ctx = TranslateContext(
                self.domainstack[-1][0] if self.domainstack else None,
                self.domainstack[-1][1] if self.domainstack else None,
                i18n_translate,
                self.domainstack[-1][2] if self.domainstack else None,
                self.filename, childs_lineno)
            if self.translatestack:
                ctx.parent = self.translatestack[-1]
                if ctx.parent is not None:
                    ctx.parent.register_child(start, ctx)
            self.translatestack.append(ctx)
        else:
            self.translatestack.append(None)

        if self.domainstack:
            i18n_attributes = attributes.get((I18N_NS, 'attributes'))
            if i18n_attributes and include_domain:
                parts = [p.strip() for p in i18n_attributes.split(';')]
                for msgid in parts:
                    if ' ' not in msgid:
                        if msgid not in plain_attrs:
                            continue
                        value, offset, post_offset = plain_attrs[msgid]
                        self.add_message(self.domainstack[-1][1], value, self.domainstack[-1][2] or '', offset=offset)
                    else:
                        try:
                            (attr, msgid) = msgid.split()
                        except ValueError:
                            continue
                        if attr not in plain_attrs:
                            continue
                        value, offset, post_offset = plain_attrs[attr]
                        self.add_message(self.domainstack[-1][1], msgid, u'Default: %s' % value, offset=offset)

            for (attribute, value) in attributes.items():
                value = decode_htmlentities(value)
                for source in self.get_code_for_attribute(attribute, value):
                    self.parse_python(source)

        self.linenumber = childs_lineno
        for child in children:
            self.visit(*child)

        if end is not None:
            self.linenumber += get_newline_count(end['prefix'] + end['name'])
            post_offset = [x[2] for x in get_plain_attrs(end['attrs']).values()]
            if post_offset:
                self.linenumber += max(post_offset)
            self.linenumber += get_newline_count(end['suffix'])

        if self.domainstack:
            self.domainstack.pop()

        translate = self.translatestack.pop()
        if translate and not translate.ignore() and translate.domain and include_domain:
            self.messages.append(translate)

    def visit_text(self, data):
        if self.target_domain is None or self.target_domain == self.domainstack[-1][0]:
            default_engine = self.config['default-engine']
            for line in data.splitlines():
                line = decode_htmlentities(line)
                try:
                    for source in get_python_expressions(line, default_engine):
                        if UNDERSCORE_CALL.search(source):
                            self.parse_python(source)
                except SyntaxError:
                    print('Aborting due to Python syntax error in %s[%d]: %s' %
                            (self.filename, self.linenumber, line))
                    sys.exit(1)
            if self.translatestack[-1]:
                self.translatestack[-1].add_text(data)
        self.linenumber += get_newline_count(data)

    def visit_comment(self, data):
        self.linenumber += get_newline_count(data)

    def visit_cdata(self, data):
        self.linenumber += get_newline_count(data)

    def visit_processing_instruction(self, data):
        self.linenumber += get_newline_count(data['text'])

    def visit_default(self, data):
        if not data.lower().startswith('<!doctype'):
            print("%s:%s\n    Warning: Node type 'default', possible bad markup" %
                    (self.filename, self.linenumber), file=sys.stderr)
        self.linenumber += get_newline_count(data)

    def add_message(self, msgctxt, msgid, comment=u'', offset=0):
        self.messages.append(Message(msgctxt, msgid, None, [], comment, u'',
            (self.filename, self.linenumber + offset)))

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
                        m = ENGINE_PREFIX.match(value)
                        if (m is not None) and (m.group(1) == 'python'):
                            m = None
                            value = value.split(':', 1)[1]
                        if m is None:
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

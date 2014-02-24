from __future__ import absolute_import
from __future__ import print_function
import collections
import re
import sys
from lxml import etree
from .python import _extract_python
from . import register_extractor
from . import Message


def _open(filename):
    """Injection point for tests."""
    return open(filename, 'rb')


WHITESPACE = re.compile(u"\s+")
EXPRESSION = re.compile(u"\s*\${(.*?)}\s*")
UNDERSCORE_CALL = re.compile("_\(.*\)")

I18N_NS = 'http://xml.zope.org/namespaces/i18n'
TAL_NS = 'http://xml.zope.org/namespaces/tal'
DEFAULT_NSMAP = {I18N_NS: 'i18n', TAL_NS: 'tal'}


class TranslateContext(object):
    def __init__(self, domain, msgid, filename, lineno, ns_map):
        self.domain = domain
        self.msgid = msgid
        self.text = []
        self.filename = filename
        self.lineno = lineno
        self.ns_map = ns_map

    def add_text(self, text):
        self.text.append(text)

    def add_element(self, element):
        name = element.attrib.get('%s:name' % self.ns_map[I18N_NS])
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


class Extractor(object):
    def __init__(self, filename, options):
        self.options = options
        self.filename = filename
        self.target_domain = options.domain
        self.messages = []
        self.domainstack = collections.deque([None])
        self.translatestack = collections.deque([None])
        self.ns_stack = collections.deque([DEFAULT_NSMAP])

    def __call__(self):
        parser = etree.HTMLParser(encoding='utf-8')
        try:
            tree = etree.parse(_open(self.filename), parser)
            for (action, element) in etree.iterwalk(tree, events=['start', 'end']):
                if action == 'start':
                    self.start(element)
                elif action == 'end':
                    self.end(element)
        except UnicodeError as e:
            print('Aborting due to parse error in %s: %s' %
                            (self.filename, e.message), file=sys.stderr)
            sys.exit(1)
        return self.messages

    def add_message(self, element, msgid, comment=u''):
        self.messages.append(Message(None, msgid, None, [], comment, u'',
            (self.filename, element.sourceline)))

    def get_code_for_attribute(self, attribute, value, ns_map):
        if attribute.startswith('%s:' % ns_map[TAL_NS]):
            attribute = attribute[len(ns_map[TAL_NS]) + 1:]
            if attribute in ['content', 'replace']:
                yield value
            elif attribute in ['define', 'repeat']:
                yield value.split(None, 1)[1]
        else:
            for source in EXPRESSION.findall(value):
                yield source

    def parse_python(self, element, message):
        msg = message
        if msg.startswith('python:'):
            msg = msg[7:]

        if isinstance(msg, unicode):
            msg = msg.encode('utf-8')
        for message in _extract_python(self.filename, msg, self.options):
            self.messages.append(Message(*message[:6],
                location=(self.filename, element.sourceline)))

    def start(self, element):
        ns_map = self.ns_stack[-1].copy()
        for (attr, value) in element.attrib.items():
            if attr.startswith('xmlns:'):
                ns_map[value] = attr[6:]
        self.ns_stack.append(ns_map)

        new_domain = element.attrib.get('%s:domain' % ns_map[I18N_NS])
        if new_domain:
            self.domainstack.append(new_domain)
        elif self.domainstack:
            self.domainstack.append(self.domainstack[-1])

        if self.translatestack[-1]:
            self.translatestack[-1].add_element(element)

        i18n_translate = element.attrib.get('%s:translate' % ns_map[I18N_NS])
        if i18n_translate is not None:
            self.translatestack.append(TranslateContext(
                self.domainstack[-1] if self.domainstack else None,
                i18n_translate, self.filename, element.sourceline,
                ns_map))
        else:
            self.translatestack.append(None)

        if not self.domainstack:
            return

        i18n_attributes = element.attrib.get('%s:attributes' % ns_map[I18N_NS])
        if i18n_attributes:
            parts = [p.strip() for p in i18n_attributes.split(';')]
            for msgid in parts:
                if ' ' not in msgid:
                    if msgid not in element.attrib:
                        continue
                    self.add_message(element, element.attrib[msgid])
                else:
                    try:
                        (attr, msgid) = msgid.split()
                    except ValueError:
                        continue
                    if attr not in element.attrib:
                        continue
                    self.add_message(element, msgid, u'Default: %s' % element.attrib[attr])

        for (attribute, value) in element.attrib.items():
            for source in self.get_code_for_attribute(attribute, value, ns_map):
                self.parse_python(element, source)

        if element.text:
            self.data(element, element.text)

    def data(self, element, data):
        for source in EXPRESSION.findall(data):
            if UNDERSCORE_CALL.search(source):
                self.parse_python(element, source)
        if not self.translatestack[-1]:
            return
        self.translatestack[-1].add_text(data)

    def end(self, tag):
        if self.ns_stack:
            self.ns_stack.pop()
        if self.domainstack:
            self.domainstack.pop()
        translate = self.translatestack.pop()
        if translate and not translate.ignore() and translate.domain and \
                (self.target_domain is None or translate.domain == self.target_domain):
            self.messages.append(translate.message())
        if tag.tail:
            self.data(tag, tag.tail)


@register_extractor('xml', ['.pt', '.zpt'])
def extract_xml(filename, options):
    extractor = Extractor(filename, options)
    return extractor()

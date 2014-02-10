from __future__ import absolute_import
from __future__ import print_function
import collections
import re
import sys
from io import BytesIO
from xml.parsers import expat
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

    def addText(self, text):
        self.text.append(text)

    def addNode(self, name, attributes):
        name = attributes.get('%s:name' % self.ns_map[I18N_NS])
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


class XmlExtractor(object):
    ENTITY = re.compile(r"&([A-Za-z]+|#[0-9]+);")

    def __call__(self, filename, options):
        self.filename = filename
        self.target_domain = options.domain
        self.options = options
        self.messages = []
        self.parser = expat.ParserCreate()
        if hasattr(self.parser, 'returns_unicode'):  # Not present in Py3
            self.parser.returns_unicode = True
        self.parser.UseForeignDTD()
        self.parser.SetParamEntityParsing(
            expat.XML_PARAM_ENTITY_PARSING_ALWAYS)
        self.parser.StartElementHandler = self.StartElementHandler
        self.parser.CharacterDataHandler = self.CharacterDataHandler
        self.parser.EndElementHandler = self.EndElementHandler
        self.parser.DefaultHandler = self.DefaultHandler
        self.domainstack = collections.deque()
        self.translatestack = collections.deque([None])
        self.ns_stack = collections.deque([DEFAULT_NSMAP])

        try:
            self.parser.ParseFile(_open(filename))
        except expat.ExpatError as e:
            print('Aborting due to parse error in %s: %s' %
                            (filename, e.message), file=sys.stderr)
            sys.exit(1)
        return self.messages

    def add_message(self, msgid, comment=u''):
        self.messages.append(Message(None, msgid, None, [], comment, u'',
            (self.filename, (self.parser.CurrentLineNumber))))

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

    def addUnderscoreCalls(self, message):
        msg = message
        if isinstance(msg, unicode):
            msg = msg.encode('utf-8')
        for message in _extract_python(self.filename, msg, self.options):
            self.messages.append(Message(*message[:6],
                location=(self.filename, self.parser.CurrentLineNumber)))

    def StartElementHandler(self, name, attributes):
        ns_map = self.ns_stack[-1].copy()
        for (attr, value) in attributes.items():
            if attr.startswith('xmlns:'):
                ns_map[value] = attr[6:]
        self.ns_stack.append(ns_map)

        new_domain = attributes.get('%s:domain' % ns_map[I18N_NS])
        if new_domain:
            self.domainstack.append(new_domain)
        elif self.domainstack:
            self.domainstack.append(self.domainstack[-1])

        if self.translatestack[-1]:
            self.translatestack[-1].addNode(name, attributes)

        i18n_translate = attributes.get('%s:translate' % ns_map[I18N_NS])
        if i18n_translate is not None:
            self.translatestack.append(TranslateContext(
                self.domainstack[-1] if self.domainstack else None,
                i18n_translate, self.filename, self.parser.CurrentLineNumber,
                ns_map))
        else:
            self.translatestack.append(None)

        if not self.domainstack:
            return

        i18n_attributes = attributes.get('%s:attributes' % ns_map[I18N_NS])
        if i18n_attributes:
            parts = [p.strip() for p in i18n_attributes.split(';')]
            for msgid in parts:
                if ' ' not in msgid:
                    if msgid not in attributes:
                        continue
                    self.add_message(attributes[msgid])
                else:
                    try:
                        (attr, msgid) = msgid.split()
                    except ValueError:
                        continue
                    if attr not in attributes:
                        continue
                    self.add_message(msgid, u'Default: %s' % attributes[attr])

        for (attribute, value) in attributes.items():
            for source in self.get_code_for_attribute(attribute, value, ns_map):
                self.addUnderscoreCalls(source)

    def DefaultHandler(self, data):
        print('DATA: %r' % data)
        if data.startswith(u'&') and self.translatestack[-1]:
            self.translatestack[-1].addText(data)

    def CharacterDataHandler(self, data):
        print('DATA: %r' % data)
        for source in EXPRESSION.findall(data):
            if UNDERSCORE_CALL.search(source):
                self.addUnderscoreCalls(source)
        if not self.translatestack[-1]:
            return

        self.translatestack[-1].addText(data)
        return
#        data_length = len(data)
#        context = self.parser.GetInputContext()
#
#        while data:
#            m = self.ENTITY.search(context)
#            if m is None or m.start() >= data_length:
#                self.translatestack[-1].addText(data)
#                break
#
#            n = self.ENTITY.match(data)
#            if n is not None:
#                length = n.end()
#            else:
#                length = 1
#
#            self.translatestack[-1].addText(context[0: m.end()])
#            data = data[m.start() + length:]

    def EndElementHandler(self, name):
        if self.ns_stack:
            self.ns_stack.pop()
        if self.domainstack:
            self.domainstack.pop()
        translate = self.translatestack.pop()
        if translate and not translate.ignore() and \
                (None in [translate.domain, self.target_domain] or translate.domain == self.target_domain):
            self.messages.append(translate.message())


@register_extractor('xml', ['.pt', '.zpt'])
def extract_xml(filename, options):
    extractor = XmlExtractor()
    return extractor(filename, options)

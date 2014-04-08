from __future__ import absolute_import
from __future__ import print_function
import collections
import re
import sys
from chameleon.namespaces import I18N_NS
from chameleon.namespaces import TAL_NS
from chameleon.program import ElementProgram
from chameleon.zpt.program import MacroProgram


from .python import _extract_python
from . import register_extractor
from . import Message


def _open(filename):
    """Injection point for tests."""
    return open(filename, 'rb')


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


class Extractor(ElementProgram):
    DEFAULT_NAMESPACES = MacroProgram.DEFAULT_NAMESPACES

    def __init__(self, filename, options):
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
        super(Extractor, self).__init__(source, filename=filename)

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

    def get_code_for_attribute(self, attribute, value):
        if attribute[0] == TAL_NS:
            if attribute[1] in ['content', 'replace']:
                yield value
            elif attribute[1] in ['define', 'repeat']:
                yield value.split(None, 1)[1]
        else:
            for source in EXPRESSION.findall(value):
                yield source

    def parse_python(self, source):
        if not isinstance(source, bytes):
            source = source.encode('utf-8')
        for message in _extract_python(self.filename, source, self.options):
            self.messages.append(Message(*message[:6],
                location=(self.filename, self.linenumber)))


@register_extractor('xml', ['.pt', '.zpt'])
def extract_xml(filename, options):
    extractor = Extractor(filename, options)
    return extractor.messages

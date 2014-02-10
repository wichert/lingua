from __future__ import absolute_import
from __future__ import print_function
import collections
import sys
from xml.parsers import expat
from . import register_extractor
from . import Message


class ZcmlExtractor(object):
    ATTRIBUTES = set(['title', 'description'])

    def __call__(self, filename, options):
        self.filename = filename
        self.target_domain = options.domain
        self.messages = []
        self.parser = expat.ParserCreate()
        self.parser.StartElementHandler = self.StartElementHandler
        self.parser.EndElementHandler = self.EndElementHandler
        self.domainstack = collections.deque()
        try:
            self.parser.ParseFile(open(filename, 'rb'))
        except expat.ExpatError as e:
            print('Aborting due to parse error in %s: %s' %
                            (filename, e.message), file=sys.stderr)
            sys.exit(1)
        return self.messages

    def add_message(self, msgid):
        self.messages.append(
                Message(None, msgid, u'', [], u'', u'',
                    (self.filename, (self.parser.CurrentLineNumber))))

    def StartElementHandler(self, name, attributes):
        if 'i18n_domain' in attributes:
            self.domainstack.append(attributes["i18n_domain"])
        elif self.domainstack:
            self.domainstack.append(self.domainstack[-1])

        if not self.domainstack:
            return

        if self.target_domain in [None, self.domainstack[-1]]:
            for (key, value) in attributes.items():
                if key in self.ATTRIBUTES:
                    self.add_message(value)

    def EndElementHandler(self, name):
        if self.domainstack:
            self.domainstack.pop()


@register_extractor('zcml', ['.zcml'])
def extract_zcml(filename, options):
    extractor = ZcmlExtractor()
    return extractor(filename, options)

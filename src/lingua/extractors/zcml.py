from __future__ import absolute_import
from __future__ import print_function
import collections
import sys
from xml.parsers import expat
from . import Extractor
from . import Message


def _open(filename):
    """Injection point for tests."""
    return open(filename, 'rb')


class ZCMLExtractor(Extractor):
    '''Zope Configuration Markup Language (ZCML)'''
    extensions = ['.zcml']
    ATTRIBUTES = set(['title', 'description'])

    def __call__(self, filename, options, fileobj=None, lineno=0):
        self.filename = filename
        self.target_domain = options.domain
        self.messages = []
        self.parser = expat.ParserCreate()
        self.parser.StartElementHandler = self.StartElementHandler
        self.parser.EndElementHandler = self.EndElementHandler
        self.domainstack = collections.deque()
        if fileobj is None:
            fileobj = _open(filename)
        try:
            self.parser.ParseFile(fileobj)
        except expat.ExpatError as e:
            print('Aborting due to parse error in %s: %s' %
                            (filename, e), file=sys.stderr)
            sys.exit(1)
        return self.messages

    def add_message(self, msgid):
        self.messages.append(
                Message(None, msgid, None, [], u'', u'',
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

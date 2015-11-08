from pkg_resources import working_set
from .python import KEYWORDS
from .python import parse_keyword
from . import EXTRACTORS
from . import Message
from . import check_c_format
from . import check_python_format
from . import Extractor
from . import update_keywords


class BabelExtractor(Extractor):
    extensions = []
    extractor = None
    default_config = {
            'comment-tags': '',
    }

    def __call__(self, filename, options, fileobj=None, firstline=0):
        self.keywords = KEYWORDS.copy()
        update_keywords(self.keywords, options.keywords)
        if fileobj is None:
            fileobj = open(filename, 'rb')
        comment_tags = self.config['comment-tags'].split()
        messages = self.extractor(fileobj, list(self.keywords.keys()),
                comment_tags, self.config)
        for (lineno, function, args, comment) in messages:
            if not isinstance(args, (list, tuple)):
                args = [args]
            args = [(None, a, lineno) for a in args]
            if function in self.keywords:
                (domain, msgctxt, msgid, msgid_plural, c) = parse_keyword(args, self.keywords[function], filename, lineno)
                if c:
                    comment.append(c)
            else:
                msgid = args[0]
                domain = msgid_plural = None

            if domain and self.options.domain and domain != self.options.domain:
                continue
            comment = u' '.join(comment)
            flags = []
            check_c_format(msgid, flags)
            check_python_format(msgid, flags)
            yield Message(msgctxt, msgid, msgid_plural, flags, comment, u'', (filename, firstline + lineno))


def register_babel_plugins():
    for entry_point in working_set.iter_entry_points('babel.extractors'):
        name = entry_point.name
        extractor = entry_point.load(require=True)
        cls = type('BabelExtractor_%s' % name,
                (BabelExtractor, object),
                {'extractor': staticmethod(extractor),
                 '__doc__': extractor.__doc__.splitlines()[0]})
        EXTRACTORS['babel-%s' % name] = cls()

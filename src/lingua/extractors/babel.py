from pkg_resources import working_set
from . import EXTRACTORS
from . import Message
from . import check_c_format
from . import check_python_format


DEFAULT_KEYWORDS = {
        '_': None,
        'gettext': None,
        'ngettext': (1, 2),
        'ugettext': None,
        'ungettext': (1, 2),
        'dgettext': (2,),
        'dngettext': (2, 3),
        'N_': None,
        'pgettext': ((1, 'c'), 2)
        }


def babel_wrapper(extractor):
    def wrapper(filename, options):
        fileobj = open(filename, 'rb')
        for (lineno, _, msgid, comment) in extractor(fileobj, DEFAULT_KEYWORDS.keys(), (), {}):
            flags = []
            check_c_format(msgid, flags)
            check_python_format(msgid, flags)
            yield Message(None, msgid, u'', flags, comment, None, (filename, lineno))
    wrapper.__doc__ = extractor.__doc__
    return wrapper


def register_babel_plugins():
    for entry_point in working_set.iter_entry_points('babel.extractors'):
        extractor = babel_wrapper(entry_point.load(require=True))
        EXTRACTORS['babel-%s' % entry_point.name] = extractor

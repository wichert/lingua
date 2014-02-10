import collections
import os


Message = collections.namedtuple('Message',
        'msgctxt msgid msgstr flags comment tcomment location')

EXTRACTORS = {}
EXTENSIONS = {}

def register_extractor(identifier, extensions):
    def wrapper(func):
        EXTRACTORS[identifier] = func
        for extension in extensions:
            EXTENSIONS[extension] = func
        return func
    return wrapper


def get_extractor(filename):
    ext = os.path.splitext(filename)[1]
    return EXTENSIONS.get(ext)

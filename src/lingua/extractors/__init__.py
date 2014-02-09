EXTRACTORS = {}
EXTENSIONS = {}

def register_extractor(identifier, extensions):
    def wrapper(func):
        EXTRACTORS[identifier] = func
        for extension in extensions:
            EXTENSIONS[extension] = func
        return func(*a, **kw)
    return wrapper


def get_extractor(filename):
    for (extension, extractor) in EXTENSIONS.items():
        if filename.endswith(extension):
            return extractor

# Python compatibility support code
# This is taken from six

# Entry points compatibility for importlib.metadata vs pkg_resources
try:
    from importlib.metadata import entry_points

    try:
        # Python 3.10+ returns SelectableGroups with select() method
        entry_points(group="test")

        def iter_entry_points(group):
            return entry_points(group=group)
    except TypeError:
        # Python 3.9 returns a dict-like object
        def iter_entry_points(group):
            eps = entry_points()
            return eps.get(group, [])

    # In importlib.metadata, entry_point.load() doesn't have require parameter.
    # Missing dependencies raise ModuleNotFoundError instead of DistributionNotFound.
    EntryPointLoadError = ModuleNotFoundError

    def load_entry_point(entry_point):
        return entry_point.load()

except ImportError:
    from pkg_resources import DistributionNotFound
    from pkg_resources import working_set

    def iter_entry_points(group):
        return working_set.iter_entry_points(group)

    EntryPointLoadError = DistributionNotFound

    def load_entry_point(entry_point):
        return entry_point.load(require=True)


def add_metaclass(metaclass):
    """Class decorator for creating a class with a metaclass."""

    def wrapper(cls):
        orig_vars = cls.__dict__.copy()
        orig_vars.pop("__dict__", None)
        orig_vars.pop("__weakref__", None)
        slots = orig_vars.get("__slots__")
        if slots is not None:
            if isinstance(slots, str):
                slots = [slots]
            for slots_var in slots:
                orig_vars.pop(slots_var)
        return metaclass(cls.__name__, cls.__bases__, orig_vars)

    return wrapper

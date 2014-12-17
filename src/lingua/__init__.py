import pkg_resources


def lingua_version():
    pkg = pkg_resources.get_distribution('lingua')
    return pkg.version

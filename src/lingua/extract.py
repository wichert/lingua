from __future__ import print_function
import argparse
import io
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
from operator import attrgetter
import os
import re
import sys
import tempfile
import time
try:
    from configparser import SafeConfigParser
except ImportError:
    from ConfigParser import SafeConfigParser
import polib
from lingua.extractors import get_extractor
from lingua.extractors import register_extractors
from lingua.extractors.babel import register_babel_plugins
from lingua.extractors import EXTRACTORS
from lingua.extractors import EXTENSIONS
from lingua import lingua_version


def po_timestamp():
    local = time.localtime()
    offset = -(time.altzone if local.tm_isdst else time.timezone)
    return '%s%s%s' % (
        time.strftime('%Y-%m-%d %H:%M', local),
        '-' if offset < 0 else '+',
        time.strftime('%H%M', time.gmtime(abs(offset))))


def _same_text(a, b):
    a = re.sub(r'\s+', u' ', a)
    b = re.sub(r'\s+', u' ', b)
    return a == b


class POEntry(polib.POEntry):
    def __init__(self, *a, **kw):
        polib.POEntry.__init__(self, *a, **kw)
        self._comments = []
        self._tcomments = []

    @property
    def comment(self):
        return u'\n'.join(self._comments)

    @comment.setter
    def comment(self, value):
        pass

    @property
    def tcomment(self):
        return u'\n'.join(self._tcomments)

    @tcomment.setter
    def tcomment(self, value):
        pass

    def __eq__(self, other):
        r = super(POEntry, self).__eq__(other)
        if not r:
            return False
        return _same_text(other.comment, self.comment) and \
            _same_text(other.tcomment, self.tcomment)

    def update(self, message, add_occurrences=True):
        if add_occurrences:
            self.occurrences.append((message.location[0], str(message.location[1])))
        self.flags.extend(f for f in message.flags if f not in self.flags)
        if message.comment not in self._comments:
            self._comments.append(message.comment)
        if message.tcomment not in self._tcomments:
            self._tcomments.append(message.tcomment)


class POFile(polib.POFile):
    copyright = None
    package_name = None

    def metadata_as_entry(self):
        entry = polib.POFile.metadata_as_entry(self)
        year = time.localtime().tm_year
        header = [u'SOME DESCRIPTIVE TITLE']
        if self.copyright_holder:
            header.append(u'Copyright (C) %d %s' % (year, self.copyright_holder))
        header.append(
                u'This file is distributed under the same license as the %s package.' %
                self.package_name)
        header.append(u'FIRST AUTHOR <EMAIL@ADDRESS>, %d.' % year)
        entry.tcomment = u'\n'.join(header)
        return entry


def no_duplicates(iterator):
    seen = set()
    for item in iterator:
        if item in seen:
            continue
        seen.add(item)
        yield item


def list_files(options):
    if options.files_from:
        for filename in open(options.files_from, 'r'):
            if filename.startswith('#') or not filename.strip():
                continue
            yield filename
    for file in options.file:
        if os.path.isfile(file):
            yield file
        elif os.path.isdir(file):
            for (dirpath, dirnames, filenames) in os.walk(file):
                for file in filenames:
                    if get_extractor(file) is not None:
                        yield os.path.join(dirpath, file)
        else:
            print('Invalid file type for %s' % file, file=sys.stderr)
            sys.exit(1)


def find_file(filename, search_path=[]):
    """Return the filename for a given file, checking search paths.
    """
    paths = [os.path.curdir] + search_path
    for path in paths:
        filename = os.path.join(path, filename)
        if os.path.isfile(filename):
            return filename
    return None


def strip_linenumbers(entry):
    seen = set()
    occurrences = []
    for location, line in entry.occurrences:
        if location in seen:
            continue
        occurrences.append((location, ''))
        seen.add(location)
    entry.occurrences = occurrences


def create_catalog(options):
    catalog = POFile(wrapwidth=options.width)
    catalog.copyright_holder = options.copyright_holder
    catalog.package_name = options.package_name
    catalog.metadata_is_fuzzy = True
    catalog.metadata = OrderedDict()
    catalog.metadata['Project-Id-Version'] = ' '.join(filter(
        None, [options.package_name, options.package_version]))
    if options.msgid_bugs_address:
        catalog.metadata['Report-Msgid-Bugs-To'] = options.msgid_bugs_address
    catalog.metadata['POT-Creation-Date'] = po_timestamp()
    catalog.metadata['PO-Revision-Date'] = 'YEAR-MO-DA HO:MI+ZONE'
    catalog.metadata['Last-Translator'] = 'FULL NAME <EMAIL@ADDRESS'
    catalog.metadata['Language-Team'] = 'LANGUAGE <LL@li.org>'
    catalog.metadata['Language'] = ''
    catalog.metadata['MIME-Version'] = '1.0'
    catalog.metadata['Content-Type'] = 'text/plain; charset=UTF-8'
    catalog.metadata['Content-Transfer-Encoding'] = '8bit'
    catalog.metadata['Generated-By'] = 'Lingua %s' % lingua_version()
    return catalog


def _register_extension(extension, extractor):
    if extractor not in EXTRACTORS:
        print('Unknown extractor %s. Check --list-extractors for available options' % extractor,
                file=sys.stderr)
        sys.exit(1)
    EXTENSIONS[extension] = extractor


def read_config(filename):
    config = SafeConfigParser()
    config.readfp(open(filename))
    for section in config.sections():
        if section == 'extensions':
            for (extension, extractor) in config.items(section):
                _register_extension(extension, extractor)
        elif section.startswith('extractor:'):
            extractor = section[10:]
            if extractor not in EXTRACTORS:
                print('Unknown extractor %s. '
                      'Check --list-extractors for available options' % extractor,
                        file=sys.stderr)
                sys.exit(1)
            extractor_config = dict(config.items(section))
            EXTRACTORS[extractor].update_config(**extractor_config)
        elif section.startswith('extension'):
            print('Use of %s section is obsolete. '
                  'Please use the "extensions" section.' % section,
                  file=sys.stderr)
            extension = section[10:]
            plugin = config.get(section, 'plugin')
            if not plugin:
                print('No plugin defined for extension %s' % extension,
                    file=sys.stderr)
            _register_extension(extension, plugin)


def _summarise(catalog):
    summary = {}
    for entry in catalog:
        if entry.obsolete:
            continue
        summary[(entry.msgid, entry.msgctxt)] = entry
    return summary


def identical(a, b):
    """Check if two catalogs are identical, ignoring metadata.
    """
    a = _summarise(a)
    b = _summarise(b)
    return a == b


def save_catalog(catalog, filename):
    if os.path.exists(filename):
        old_catalog = None
        try:
            old_catalog = polib.pofile(filename)
        except (OSError, UnicodeDecodeError):
            pass
        if old_catalog is not None and identical(catalog, old_catalog):
            print("No changes found - not replacing %s" % filename)
            return
    (fd, tmpfile) = tempfile.mkstemp(dir=os.path.dirname(filename), text=True)
    output = io.open(fd, 'wt', encoding=catalog.encoding)
    output.write(catalog.__unicode__())
    output.close()
    os.rename(tmpfile, filename)


def main():
    parser = argparse.ArgumentParser(
            description='Extract translateable strings.')

    parser.add_argument('-c', '--config', metavar='CONFIG',
            help='Read configuration from CONFIG file')
    # Input options
    parser.add_argument('-f', '--files-from', metavar='FILE',
            help='Get list of files to process from FILE')
    parser.add_argument('-D', '--directory', metavar='DIRECTORY',
            action='append', default=[],
            help='Add DIRECTORY to list of paths to check for input files')
    parser.add_argument('file', nargs='*',
            help='Source file to process')
    parser.add_argument('--list-extractors', action='store_true',
            help='List all known extraction plugins')
    # Output options
    parser.add_argument('-o', '--output', metavar='FILE',
            default='messages.pot',
            help='Filename for generated POT file')
    parser.add_argument('--no-location',
            action='store_false', dest='location',
            help='Do not include location information')
    parser.add_argument('--no-linenumbers',
            action='store_true', dest='no_linenumbers',
            help='Do not include line numbers in location information')
    parser.add_argument('-n', '--add-location',
            action='store_true', dest='location', default=True,
            help='Include location information (default)')
    parser.add_argument('-w', '--width', metavar='NUMBER',
            default=79,
            help='Output width')
    parser.add_argument('-s', '--sort-output',  # babel compatibility
            action='store_const', const='msgid', dest='sort',
            help='Order messages by their msgid')
    parser.add_argument('-F', '--sort-by-file',
            action='store_const', const='location', dest='sort',
            help='Order messages by file location')
    # Extraction configuration
    parser.add_argument('-d', '--domain',
            help='Domain to extract')
    parser.add_argument('-k', '--keyword', metavar='WORD',
            dest='keywords', action='append', default=[], nargs='?',
            help='Look for WORD as additional keyword')
    parser.add_argument('-C', '--add-comments', metavar='TAG',
            dest='comment_tag', const=True, nargs='?',
            help='Add comments prefixed by TAG to messages, or all if no tag is given')
    # POT metadata
    parser.add_argument('--copyright-holder', metavar='STRING',
            help='Specifies the copyright holder for the texts')
    parser.add_argument('--package-name', metavar='NAME',
            default=u'PACKAGE',
            help='Package name to use in the generated POT file')
    parser.add_argument('--package-version', metavar='Version',
            default='1.0',
            help='Package version to use in the generated POT file')
    parser.add_argument('--msgid-bugs-address', metavar='EMAIL',
            help='Email address bugs should be send to')

    options = parser.parse_args()
    register_extractors()
    register_babel_plugins()

    if options.list_extractors:
        for extractor in sorted(EXTRACTORS):
            print('%-17s %s' % (extractor, EXTRACTORS[extractor].__doc__ or ''))
        return

    if options.config:
        read_config(options.config)
    else:
        user_home = os.path.expanduser('~')
        global_config = os.path.join(user_home, '.config', 'lingua')
        if os.path.exists(global_config):
            read_config(global_config)

    catalog = create_catalog(options)

    scanned = 0
    for filename in no_duplicates(list_files(options)):
        real_filename = find_file(filename, options.directory)
        if real_filename is None:
            print('Can not find file %s' % filename, file=sys.stderr)
            sys.exit(1)
        extractor = get_extractor(real_filename)
        if extractor is None:
            print('No extractor available for file %s' % filename, file=sys.stderr)
            sys.exit(1)

        for message in extractor(real_filename, options):
            entry = catalog.find(message.msgid, msgctxt=message.msgctxt)
            if entry is None:
                entry = POEntry(msgctxt=message.msgctxt,
                                msgid=message.msgid)
                if message.msgid_plural:
                    entry.msgid_plural = message.msgid_plural
                    entry.msgstr_plural[0] = ''
                    entry.msgstr_plural[1] = ''
                catalog.append(entry)
            entry.update(message, add_occurrences=options.location)
        scanned += 1
    if not scanned:
        print('No files scanned, aborting', file=sys.stderr)
        sys.exit(1)
    if not catalog:
        print('No translatable strings found, aborting', file=sys.stderr)
        sys.exit(2)

    if options.sort == 'msgid':
        catalog.sort(key=attrgetter('msgid'))
    elif options.sort == 'location':
        # Order the occurrences themselves, so the output is consistent
        catalog.sort(key=lambda m: m.occurrences.sort() or m.occurrences)

    if options.no_linenumbers:
        for entry in catalog:
            strip_linenumbers(entry)

    save_catalog(catalog, options.output)


if __name__ == '__main__':
    main()

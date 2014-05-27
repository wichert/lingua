from __future__ import print_function
import argparse
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
import os
import sys
import time
try:
    from configparser import SafeConfigParser
except ImportError:
    from ConfigParser import SafeConfigParser
import polib
from lingua.extractors import get_extractor
from lingua.extractors.babel import register_babel_plugins
from lingua.extractors import EXTRACTORS
from lingua.extractors import EXTENSIONS
import lingua.extractors.python
import lingua.extractors.xml
import lingua.extractors.zcml

lingua.extractors.python  # Keep PyFlakes happy
lingua.extractors.xml
lingua.extractors.zcml


def po_timestamp():
    local = time.localtime()
    offset = -(time.altzone if local.tm_isdst else time.timezone)
    return '%s%s%s' % (
        time.strftime('%Y-%m-%d %H:%M', local),
        '-' if offset < 0 else '+',
        time.strftime('%H%M', time.gmtime(abs(offset))))


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

    def update(self, message):
        self.occurrences.append(message.location)
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
    return catalog


def read_config(options):
    config = SafeConfigParser()
    config.readfp(open(options.config))
    for section in config.sections():
        if section.startswith('extension:'):
            extension = section[10:]
        plugin = config.get(section, 'plugin')
        if not plugin:
            print('No plugin defined for extension %s' % extension,
                    file=sys.stderr)
            sys.exit(1)
        try:
            EXTENSIONS[extension] = EXTRACTORS[plugin]
        except KeyError:
            print('Unknown plugin %s. Check --list-plugins for available options' % plugin,
                    file=sys.stderr)
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
            description='Extract translateable strings.')

    parser.add_argument('-c', '--config', metavar='CONFIG',
            help='Read plugin configuration from CONFIG file')
    # Input options
    parser.add_argument('-f', '--files-from', metavar='FILE',
            help='Get list of files to process from FILE')
    parser.add_argument('-D', '--directory', metavar='DIRECTORY',
            action='append', default=[],
            help='Add DIRECTORY to list of paths to check for input files')
    parser.add_argument('file', nargs='*',
            help='Source file to process')
    parser.add_argument('--list-plugins', action='store_true',
            help='List all known extraction plugins')
    # Output options
    parser.add_argument('-o', '--output', metavar='FILE',
            default='messages.pot',
            help='Filename for generated POT file')
    parser.add_argument('--no-location',
            action='store_false', dest='location',
            help='Do not include location information')
    parser.add_argument('-n', '--add-location',
            action='store_true', dest='location', default=True,
            help='Do not include location information')
    parser.add_argument('-w', '--width', metavar='NUMBER',
            default=79,
            help='Output width')
    # Extraction configuration
    parser.add_argument('-d', '--domain',
            help='Domain to extract')
    parser.add_argument('-k', '--keyword', metavar='WORD',
            dest='keywords', action='append', default=[], nargs='?',
            help='Look for WORD as additional keyword')
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
    register_babel_plugins()

    if options.list_plugins:
        for plugin in sorted(EXTRACTORS):
            print(plugin)
        return

    if options.config:
        read_config(options)
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
                                msgid=message.msgid,
                                msgid_plural=message.msgid_plural)
                catalog.append(entry)
            entry.update(message)
        scanned += 1
    if not scanned:
        print('No files scanned, aborting', file=sys.stderr)
        sys.exit(1)
    if not catalog:
        print('No translatable strings found, aborting', file=sys.stderr)
        sys.exit(2)
    catalog.save(options.output)


if __name__ == '__main__':
    main()

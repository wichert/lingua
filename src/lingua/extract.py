from __future__ import print_function
import argparse
import collections
import datetime
import os
import polib
import sys
from lingua.extractors import get_extractor
from lingua.extractors.babel import register_babel_plugins
import lingua.extractors.xml
import lingua.extractors.zcml


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
            yield filename
    for file in options.file:
        yield file


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
    catalog = polib.POFile(wrapwidth=options.width)
    catalog.metadata_is_fuzzy = True
    catalog.metadata = collections.OrderedDict()
    catalog.metadata['Project-Id-Version'] = ' '.join(filter(
        None, [options.package_name, options.package_version]))
    if options.msgid_bugs_address:
        catalog.metadata['Report-Msgid-Bugs-To'] = options.msgid_bugs_address
    catalog.metadata['POT-Creation-Date'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    catalog.metadata['PO-Revision-Date'] = 'YEAR-MO-DA HO:MI+ZONE'
    catalog.metadata['Last-Translator'] = 'FULL NAME <EMAIL@ADDRESS'
    catalog.metadata['Language-Team'] = 'LANGUAGE <LL@li.org>'
    catalog.metadata['Language'] = ''
    catalog.metadata['MIME-Version'] = '1.0'
    catalog.metadata['Content-Type'] = 'text/plain; charset=UTF-8'
    catalog.metadata['Content-Transfer-Encoding'] = '8bit'
    return catalog


def main():
    parser = argparse.ArgumentParser(
            description='Extract translateable strings.')

    # Input options
    parser.add_argument('-f', '--files-from', metavar='FILE',
            help='Get list of files to process from FILE')
    parser.add_argument('-D', '--directory', metavar='DIRECTORY',
            action='append', default=[],
            help='Add DIRECTORY to list of paths to check for input files')
    parser.add_argument('file', nargs='*',
            help='Source file to process')
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
    # POT metadata
    parser.add_argument('--copyright-holder', metavar='STRING',
            help='Specifies the copyright holder for the texts')
    parser.add_argument('--package-name', metavar='NAME',
            help='Package name to use in the generated POT file')
    parser.add_argument('--package-version', metavar='Version',
            default='1.0',
            help='Package version to use in the generated POT file')
    parser.add_argument('--msgid-bugs-address', metavar='EMAIL',
            help='Email address bugs should be send to')

    options = parser.parse_args()
    register_babel_plugins()
    catalog = create_catalog(options)

    for filename in no_duplicates(list_files(options)):
        real_filename = find_file(filename, options.directory)
        if real_filename is None:
            print('Can not find file %s' % filename, file=sys.stderr)
            sys.exit(1)
        extractor = get_extractor(real_filename)
        if extractor is None:
            print('No extractor available for file %s' % filename, file=sys.stderr)
            sys.exit(1)

        for (lineno, function, msg_id, comments) in extractor(real_filename, options):
            msg = catalog.find(msg_id)
            if msg is None:
                msg = polib.POEntry(msgid=msg_id)
                catalog.append(msg)
            if options.location:
                msg.occurrences.append((filename, lineno))
            if comments:
                if msg.comment:
                    msg.comment += '\n'
                msg.comment += '\n'.join(comments)
        catalog.save('messages.pot')


if __name__ == '__main__':
    main()

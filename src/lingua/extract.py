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
import click
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
    return "%s%s%s" % (
        time.strftime("%Y-%m-%d %H:%M", local),
        "-" if offset < 0 else "+",
        time.strftime("%H%M", time.gmtime(abs(offset))),
    )


def _same_text(a, b):
    a = re.sub(r"\s+", u" ", a)
    b = re.sub(r"\s+", u" ", b)
    return a == b


class POEntry(polib.POEntry):
    def __init__(self, *a, **kw):
        polib.POEntry.__init__(self, *a, **kw)
        self._comments = []
        self._tcomments = []

    @property
    def comment(self):
        return u"\n".join(self._comments)

    @comment.setter
    def comment(self, value):
        pass

    @property
    def tcomment(self):
        return u"\n".join(self._tcomments)

    @tcomment.setter
    def tcomment(self, value):
        pass

    def __eq__(self, other):
        r = super(POEntry, self).__eq__(other)
        if not r:
            return False
        return _same_text(other.comment, self.comment) and _same_text(
            other.tcomment, self.tcomment
        )

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
        header = [u"SOME DESCRIPTIVE TITLE"]
        if self.copyright_holder:
            header.append(u"Copyright (C) %d %s" % (year, self.copyright_holder))
        header.append(
            u"This file is distributed under the same license as the %s package."
            % self.package_name
        )
        header.append(u"FIRST AUTHOR <EMAIL@ADDRESS>, %d." % year)
        entry.tcomment = u"\n".join(header)
        return entry


def no_duplicates(iterator):
    seen = set()
    for item in iterator:
        if item in seen:
            continue
        seen.add(item)
        yield item


def list_files(files_from, sources):
    if files_from:
        for filename in files_from:
            if filename.startswith("#") or not filename.strip():
                continue
            yield filename
    for file in sources:
        if os.path.isfile(file):
            yield file
        elif os.path.isdir(file):
            for (dirpath, dirnames, filenames) in os.walk(file):
                for file in filenames:
                    if get_extractor(file) is not None:
                        yield os.path.join(dirpath, file)
        else:
            click.echo("Invalid file type for %s" % file, err=True)
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
        occurrences.append((location, ""))
        seen.add(location)
    entry.occurrences = occurrences


def create_catalog(
    width, copyright_holder, package_name, package_version, msgid_bugs_address
):
    catalog = POFile(wrapwidth=width)
    catalog.copyright_holder = copyright_holder
    catalog.package_name = package_name
    catalog.metadata_is_fuzzy = True
    catalog.metadata = OrderedDict()
    catalog.metadata["Project-Id-Version"] = " ".join(
        filter(None, [package_name, package_version])
    )
    if msgid_bugs_address:
        catalog.metadata["Report-Msgid-Bugs-To"] = msgid_bugs_address
    catalog.metadata["POT-Creation-Date"] = po_timestamp()
    catalog.metadata["PO-Revision-Date"] = "YEAR-MO-DA HO:MI+ZONE"
    catalog.metadata["Last-Translator"] = "FULL NAME <EMAIL@ADDRESS"
    catalog.metadata["Language-Team"] = "LANGUAGE <LL@li.org>"
    catalog.metadata["Language"] = ""
    catalog.metadata["MIME-Version"] = "1.0"
    catalog.metadata["Content-Type"] = "text/plain; charset=UTF-8"
    catalog.metadata["Content-Transfer-Encoding"] = "8bit"
    catalog.metadata["Generated-By"] = "Lingua %s" % lingua_version()
    return catalog


def _register_extension(extension, extractor):
    if extractor not in EXTRACTORS:
        click.echo(
            "Unknown extractor %s. Check --list-extractors for available options"
            % extractor,
            err=True,
        )
        sys.exit(1)
    EXTENSIONS[extension] = extractor


def read_config(cfg_file):
    config = SafeConfigParser()
    config.readfp(cfg_file)
    for section in config.sections():
        if section == "extensions":
            for (extension, extractor) in config.items(section):
                _register_extension(extension, extractor)
        elif section.startswith("extractor:"):
            extractor = section[10:]
            if extractor not in EXTRACTORS:
                click.echo(
                    "Unknown extractor %s. "
                    "Check --list-extractors for available options" % extractor,
                    err=True,
                )
                sys.exit(1)
            extractor_config = dict(config.items(section))
            EXTRACTORS[extractor].update_config(**extractor_config)
        elif section.startswith("extension"):
            click.echo(
                "Use of %s section is obsolete. "
                'Please use the "extensions" section.' % section,
                err=True,
            )
            extension = section[10:]
            plugin = config.get(section, "plugin")
            if not plugin:
                click.echo("No plugin defined for extension %s" % extension, err=True)
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
            click.echo("No changes found - not replacing %s" % filename)
            return
    (fd, tmpfile) = tempfile.mkstemp(dir=os.path.dirname(filename), text=True)
    output = io.open(fd, "wt", encoding=catalog.encoding)
    output.write(catalog.__unicode__())
    output.close()
    os.rename(tmpfile, filename)


def _location_sort_key(msg):
    locations = [(fn, int(line)) for (fn, line) in msg.occurrences]
    locations.sort()  # Sort so first occurence is always used.
    return locations


class ExtractorOptions:
    def __init__(self, comment_tag, domain, keywords):
        self.comment_tag = comment_tag
        self.domain = domain
        self.keywords = keywords


@click.command()
@click.option(
    "-c",
    "--config",
    "cfg_file",
    metavar="CONFIG",
    help="Read configuration from CONFIG file",
    type=click.File(),
)
# Input options
@click.option(
    "-f",
    "--files-from",
    metavar="FILE",
    type=click.File(),
    help="Get list of files to process from FILE",
)
@click.option(
    "-D",
    "--directory",
    metavar="DIRECTORY",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    multiple=True,
    help="Add DIRECTORY to list of paths to check for input files",
)
@click.argument("sources", nargs=-1, type=click.Path(exists=True))
@click.option(
    "--list-extractors", is_flag=True, help="List all known extraction plugins"
)
# Output options
@click.option(
    "-o",
    "--output",
    metavar="FILE",
    type=click.Path(exists=False, dir_okay=False, writable=True),
    default="messages.pot",
    help="Filename for generated POT file",
)
@click.option(
    "--add-location/--no-location",
    "location",
    default=True,
    help="Include location information",
)
@click.option(
    "--linenumbers/--no-linenumbers",
    default=True,
    help="Include line numbers in location information",
)
@click.option("-w", "--width", metavar="NUMBER", default=79, help="Output width")
@click.option(
    "-s",
    "--sort-output",
    "sort_order",  # babel compatibility
    flag_value="msgid",
    help="Order messages by their msgid",
)
@click.option(
    "-F",
    "--sort-by-file",
    "sort_order",
    flag_value="location",
    help="Order messages by file location",
)
# Extraction configuration
@click.option("-d", "--domain", help="Domain to extract")
@click.option(
    "-k",
    "--keyword",
    "keywords",
    metavar="WORD",
    multiple=True,
    help="Look for WORD as additional keyword",
)
@click.option(
    "-C",
    "--add-comments",
    "comment_tag",
    metavar="TAG",
    help="Add comments prefixed by TAG to messages, or all if no tag is given",
)
# POT metadata
@click.option(
    "--copyright-holder",
    metavar="STRING",
    help="Specifies the copyright holder for the texts",
)
@click.option(
    "--package-name",
    metavar="NAME",
    default=u"PACKAGE",
    help="Package name to use in the generated POT file",
)
@click.option(
    "--package-version",
    metavar="Version",
    default="1.0",
    help="Package version to use in the generated POT file",
)
@click.option(
    "--msgid-bugs-address", metavar="EMAIL", help="Email address bugs should be send to"
)
def main(
    cfg_file,
    files_from,
    directory,
    sources,
    list_extractors,
    output,
    location,
    linenumbers,
    width,
    sort_order,
    domain,
    keywords,
    comment_tag,
    copyright_holder,
    package_name,
    package_version,
    msgid_bugs_address,
):
    "Extract translateable strings."
    directory = list(directory)
    register_extractors()
    register_babel_plugins()

    if comment_tag is None:
        comment_tag = True
    if list_extractors:
        for extractor in sorted(EXTRACTORS):
            click.echo("%-17s %s" % (extractor, EXTRACTORS[extractor].__doc__ or ""))
        return

    if cfg_file:
        read_config(cfg_file)
    else:
        user_home = os.path.expanduser("~")
        global_config = os.path.join(user_home, ".config", "lingua")
        if os.path.exists(global_config):
            read_config(open(global_config, "r"))

    catalog = create_catalog(
        width, copyright_holder, package_name, package_version, msgid_bugs_address
    )

    scanned = 0
    for filename in no_duplicates(list_files(files_from, sources)):
        real_filename = find_file(filename, directory)
        if real_filename is None:
            click.echo("Can not find file %s" % filename, err=True)
            sys.exit(1)
        extractor = get_extractor(real_filename)
        if extractor is None:
            click.echo("No extractor available for file %s" % filename, err=True)
            sys.exit(1)

        extractor_options = ExtractorOptions(
            comment_tag=comment_tag, domain=domain, keywords=keywords,
        )
        for message in extractor(real_filename, extractor_options):
            entry = catalog.find(message.msgid, msgctxt=message.msgctxt)
            if entry is None:
                entry = POEntry(msgctxt=message.msgctxt, msgid=message.msgid)
                if message.msgid_plural:
                    entry.msgid_plural = message.msgid_plural
                    entry.msgstr_plural[0] = ""
                    entry.msgstr_plural[1] = ""
                catalog.append(entry)
            entry.update(message, add_occurrences=location)
        scanned += 1
    if not scanned:
        click.echo("No files scanned, aborting", err=True)
        sys.exit(1)
    if not catalog:
        click.echo("No translatable strings found, aborting", err=True)
        sys.exit(2)

    if sort_order == "msgid":
        catalog.sort(key=attrgetter("msgid"))
    elif sort_order == "location":
        catalog.sort(key=_location_sort_key)

    if not linenumbers:
        for entry in catalog:
            strip_linenumbers(entry)

    save_catalog(catalog, output)


if __name__ == "__main__":
    main()

import click
import collections
import textwrap
import polib


def verify_po(path, show_path):
    leader = "[%s] " % path if show_path else ""
    try:
        catalog = polib.pofile(path)
    except UnicodeDecodeError:
        click.echo("Character encoding problems occured while parsing %s" % path)
        click.echo("Perhaps this is not a PO file?")
        return
    msgids = collections.defaultdict(int)
    reverse_map = collections.defaultdict(list)

    for entry in catalog:
        key = (entry.msgctxt, entry.msgid)
        msgids[key] += 1
        if entry.msgstr:
            reverse_map[entry.msgstr].append(key)

    for (key, count) in msgids.items():
        if count == 1:
            continue
        click.echo("%sMessage repeated %d times:" % (leader, count))
        (context, msgid) = key
        if context:
            msgid = u"[%s] %s" % (context, msgid)
        click.echo(
            textwrap.fill(msgid, initial_indent=u" " * 5, subsequent_indent=u" " * 8)
        )
        click.echo()

    for (msgstr, keys) in reverse_map.items():
        if len(keys) == 1:
            continue

        click.echo("%sTranslation:" % leader)
        click.echo(
            textwrap.fill(msgstr, initial_indent=u" " * 8, subsequent_indent=u" " * 8)
        )
        click.echo("Used for %d canonical texts:" % len(keys))
        for (idx, info) in enumerate(keys):
            (context, msgid) = info
            if context:
                msgid = u"[%s] %s" % (context, msgid)
            click.echo(
                textwrap.fill(
                    msgid, initial_indent="%-8d" % (idx + 1), subsequent_indent=8 * " "
                )
            )
        click.echo()


@click.command()
@click.argument("input", nargs=-1, type=click.Path(exists=True), metavar="PO-file")
def main(input):
    "Perform sanity checks on PO files"

    show_path = len(input) > 1
    for path in input:
        verify_po(path, show_path)

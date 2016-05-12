import polib
from lingua.extract import POEntry
from lingua.extract import POFile
from lingua.extract import identical
from lingua.extract import strip_linenumbers


STRIPPED_LINENUMBERS_PO = """\
#: file.txt
msgid "A"
msgstr ""
"""


class Test_identical:
    def test_ignore_metadata_differences(self):
        a = POFile()
        a.metadata['Last-Translator'] = u'Jane'
        b = polib.POFile()
        b.metadata['Last-Translator'] = u'Alice'
        assert identical(a, b)

    def test_identical_entries(self):
        a = POFile()
        b = polib.POFile()
        a.append(POEntry(msgid=u'id 1'))
        b.append(polib.POEntry(msgid=u'id 1'))
        assert identical(a, b)
        a.append(POEntry(msgid=u'id 1', msgctxt='form'))
        assert not identical(a, b)
        b.append(polib.POEntry(msgid=u'id 1', msgctxt='form'))
        assert identical(a, b)

    def test_comment_change(self):
        a = POFile()
        b = polib.POFile()
        a.append(POEntry(msgid=u'id'))
        a[0]._comments.append(u'Comment')
        b.append(polib.POEntry(msgid=u'id'))
        assert not identical(a, b)
        b[0].comment = u'Comment'
        assert identical(a, b)

    def test_tcomment_change(self):
        a = POFile()
        b = polib.POFile()
        a.append(POEntry(msgid=u'id'))
        a[0]._tcomments.append(u'Comment')
        b.append(polib.POEntry(msgid=u'id'))
        assert not identical(a, b)
        b[0].tcomment = u'Comment'
        assert identical(a, b)

    def test_ignore_comment_whitespace_change(self):
        a = POFile()
        b = polib.POFile()
        a.append(POEntry(msgid=u'id'))
        a[0]._comments.append(u'Comment one')
        b.append(polib.POEntry(msgid=u'id'))
        b[0].comment = u'Comment\none'
        assert identical(a, b)

    def test_strip_linenumbers(self):
        a = POFile()
        b = polib.pofile(STRIPPED_LINENUMBERS_PO)
        a.append(POEntry(msgid=u'A', occurrences=[('file.txt', '1')]))
        for entry in a:
            strip_linenumbers(entry)
        assert identical(a, b)

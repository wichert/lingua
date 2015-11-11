What is lingua?
===============

Lingua is a package with tools to extract translatable texts from
your code, and to check existing translations. It replaces the use
of the ``xgettext`` command from gettext, or ``pybabel`` from Babel.


Message extraction
==================

The simplest way to extract all translatable messages is to point the
``pot-create`` tool at the root of your source tree.

::

     $ pot-create src

This will create a ``messages.pot`` file containing all found messages.


Specifying input files
----------------------

There are three ways to tell lingua which files you want it to scan:

1. Specify filenames directly on the command line. For example::

   $ pot-create main.py utils.py

2. Specify a directory on the command line. Lingua will recursively scan that
   directory for all files it knows how to handle.

   ::

       $ pot-create src

3. Use the ``--files-from`` parameter to point to a file with a list of
   files to scan. Lines starting with ``#`` and empty lines will be ignored.

   ::

       $ pot-create --files-from=POTFILES.in

You can also use the ``--directory=PATH`` parameter to add the given path to the
list of directories to check for files. This may sound confusing, but can be
useful. For example this command will look for ``main.py`` and ``utils.py`` in
the current directory, and if they are not found there in the ``../src``
directory::


    $ pot-create --directory=../src main.py utils.py


Configuration
-------------

In its default configuration lingua will use its python extractor for ``.py``
files, its XML extractor for ``.pt`` and ``.zpt`` files and its ZCML extractor
for ``.zcml`` files. If you use different extensions you setup a configuration
file which tells lingua how to process files. This file uses a simple ini-style
format.

There are two types of configuration that can be set in the configuration file:
which extractor to use for a file extension, and the configuration for a single
extractor.

File extensions are configured in the ``extensions`` section. Each entry in
this section maps a file extension to an extractor name. For example to
tell lingua to use its XML extractor for files with a ``.html`` extension
you can use this configuration::

    [extensions]
    .html = xml

To find out which extractors are available use the ``-list-extractors`` option.

::

    $ bin/pot-create --list-extractors
    chameleon         Chameleon templates (defaults to Python expressions)
    python            Python sources
    xml               Chameleon templates (defaults to Python expressions)
    zcml              Zope Configuration Markup Language (ZCML)
    zope              Zope templates (defaults to TALES expressions)

A section named `extractor:<name>` can be used to configure a specific
extractor. For example to tell the XML extractor that the default language
used for expressions is TALES instead of Python::

    [extractor:xml]
    default-engine = tales

Either place a global configuration file named ``.config/lingua`` to your
home folder or use the ``--config`` option to point lingua to your
configuration file.

::

    $ pot-create -c lingua.cfg src


Domain filtering
----------------

When working with large systems you may use multiple translation domains
in a single source tree. Lingua can support that by filtering messages by
domain when scanning sources. To enable domain filtering use the ``-d`` option:

::

    $ pot-create -d mydomain src

Lingua will always include messages for which it can not determine the domain.
For example, take this Python code:

::

     print(gettext(u'Hello, World'))
     print(dgettext('mydomain', u'Bye bye'))

The first hello-message does not specify its domain and will always be
included. The second line uses `dgettext
<http://docs.python.org/2/library/gettext#gettext.dgettext>`_ to explicitly
specify the domain. Lingua will use this information when filtering domains.


Including comments
------------------

You can add comments to messages to help translators, for example to explain
how a text is used, or provide hints on how it should be translated. For
chameleon templates this can be done using the ``i18n:comment`` attribute:

::

   <label i18n:comment="This is a form label" i18n:translate="">Password</label>

Comments are inherited, so you can put them on a parent element as well.

::

   <form i18n:comment="This is used in the password reset form">
     <label i18n:translate="">Password</label>
     <button i18n:translate="">Change</button>
   </form>


For Python code you can tell lingua to include comments by using the
``--add-comments`` option. This will make Linua include all comments on the
line(s) *immediately preceeding* (there may be no empty line in between) a
translation call.

::

    # This text should address the user directly.
    return _('Thank you for using our service.')

Alternatively you can also put a comment at the end of the line starting your
translation function call.

::

    return _('Thank you for using our service.')  # Address the user directly

If you do not want all comments to be included but only specific ones you can
add a keyword to the ``--add-comments`` option, for example ``--add-comments=I18N``.

::

    # I18N This text should address the user directly, and use formal addressing.
    return _('Thank you for using our service')


Setting message flags in comments
---------------------------------

Messages can have *flags*. These are to indicate what format a message has, and
are typically used by validation tools to check if a translation does not break
variable references or template syntax. Lingua does a reasonable job to detect
strings using C and Python formatting, but sometimes you may need to set flags
yourself. This can be done with a ``[flag, flag]`` marker in a comment.

::

    # I18N [markdown,c-format]
    header =  _(u'# Hello *%s*')



Specifying keywords
-------------------

When looking for messages a lingua parser uses a default list of keywords
to identify translation calls. You can add extra keywords via the ``--keyword``
option. If you have your own ``mygettext`` function which takes a string
to translate as its first parameter you can use this:

::

    $ pot-create --keyword=mygettext

If your function takes more parameters you will need to tell lingua about them.
This can be done in several ways:

* If the translatable text is not the first parameter you can specify the
  parameter number with ``<keyword>:<parameter number>``. For example if
  you use ``i18n_log(level, msg)`` the keyword specifier would be ``i18n_log:2``
* If you support plurals you can specify the parameter used for the plural message
  by specifying the parameter number for both the singular and plural text. For
  example if your function signature is ``show_result(single, plural)`` the
  keyword specifier is ``show_result:1,2``
* If you use message contexts you can specify the parameter used for the context
  by adding a ``c`` to the parameter number. For example the keyword specifier for
  ``pgettext`` is ``pgettext:1c,2``.
* If your function takes the domain as a parameter you can specify which parameter
  is used for the domain by adding a ``d`` to the parameter number. For example
  the keyword specifier for ``dgettext`` is ``dgettext:1d,2``. This is a
  lingua-specified extension.
* You can specify the exact number of parameters a function call must have
  using the ``t`` postfix. For example if a function *must* have four parameters
  to be a valid call, the specifier could be ``myfunc:1,4t``.


Extractors
==========

Lingua includes a number of extractors:

* `python`: handles Python source code.
* `chameleon`: handles `Chameleon <http://www.pagetemplates.org/>`_ files,
  using the `Zope i18n syntax
  <https://chameleon.readthedocs.org/en/latest/reference.html#id51>`_
* `zcml`: handles Zope Configuration Markup Language (ZCML) files.
* `zope`: a variant of the chameleon extractor, which assumes the default
   expression language is `TALES
   <https://chameleon.readthedocs.org/en/latest/reference.html#expressions-tales>`_
   instead of Python.
* `xml`: old name for the `chameleon` extractor. This name should not be used
  anymore and is only supported for backwards compatibility.

Babel extractors
----------------

There are several packages with plugins for `Babel
<http://babel.edgewall.org/>`_'s message extraction tool. Lingua can use those
plugins as well. The plugin names will be prefixed with ``babel-`` to
distinguish them from lingua extractors.

For example, if you have the `PyBabel-json
<https://pypi.python.org/pypi/PyBabel-json>`_ package installed you can
instruct lingua to use it for .json files by adding this to your configuration
file::

     [extensions]
     .json = babel-json

Some Babel plugins require you to specify comment tags. This can be set with
the ``comment-tags`` option.

::

    [extractor:babel-mako]
    comment-tags = TRANSLATOR:


Comparison to other tools
=========================

Differences compared to `GNU gettext <https://www.gnu.org/software/gettext/>`_:

* Support for file formats such as Zope Page Templates (popular in
  `Pyramid <http://docs.pylonsproject.org/projects/pyramid/en/latest/>`_,
  `Chameleon`_,
  `Plone <http://plone.org/>`_ and `Zope <http://www.zope.org>`_).
* Better support for detecting format strings used in Python.
* No direct support for C, C++, Perl, and many other languages. Lingua focuses
  on languages commonly used in Python projects, although support for other
  languages can be added via plugins.


Differences compared to `Babel`_:

* More reliable detection of Python format strings.
* Lingua includes plural support.
* Support for only extracting texts for a given translation domain. This is
  often useful for extensible software where you use multiple translation
  domains in a single application.


Validating translations
=======================

Lingua includes a simple ``polint`` tool which performs a few basic checks on
PO files. Currently implemented tests are:

* duplicated message ids (can also be checked with GNU gettext's ``msgfmt``).
  These should never happen and are usually a result of a bug in the message
  extraction logic.

* identical translations used for multiple canonical texts. This can happen
  for valid reasons, for example when the original text is not spelled
  consistently.

To check a po file simply run ``polint`` with the po file as argument::

    $ polint nl.po

    Translation:
        ${val} ist keine Zeichenkette
    Used for 2 canonical texts:
    1       ${val} is not a string
    2       "${val}" is not a string


Writing custom extractors
=========================

First we need to create the custom extractor::

    from lingua.extractors import Extractor
    from lingua.extractors import Message

    class MyExtractor(Extractor):
        '''One-line description for --list-extractors'''
        extensions = ['.txt']

        def __call__(self, filename, options):
            return [Message(None, 'msgid', None, [], u'', u'', (filename, 1))]

Hooking up extractors to lingua is done by ``lingua.extractors`` entry points
in ``setup.py``::

    setup(name='mypackage',
          ...
          install_requires=[
              'lingua',
          ],
          ...
          entry_points='''
          [lingua.extractors]
          my_extractor = mypackage.extractor:MyExtractor
          '''
          ...)

Note - the registered extractor must be a class derived from the ``Extractor``
base class.

After installing ``mypackage`` lingua will automatically detect the new custom
extractor.


Helper Script
=============

There exists a helper shell script for managing translations of packages in
``docs/examples`` named ``i18n.sh``. Copy it to package root where you want to
work on translations, edit the configuration params inside the script and use::

    ./i18n.sh lang

for initial catalog creation and::

    ./i18n.sh

for updating translation and compiling the catalog.

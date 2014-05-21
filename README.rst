What is lingua?
===============

Lingua is a package with tools to extract translateable texts from
your code, and to check existing translations. It replaces the use
of the ``xgettext`` command from gettext, or ``pybabel`` from Babel.


Message extraction
==================

The simplest way to extract all translateable messages is to point the
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

This minimal configuration tells lingua to use its XML extractor for files with
the ``.html`` extension::

    [extension:.html]
    plugin = xml

Use the ``--config`` option to point lingua to your configuration file.

::

    $ pot-create -c lingua.cfg src

This also allows you to use Babel extraction plugins available on your system.
To prevent naming conflicts you need to prefix the name of a babel plugin with
``babel-``. This file can be used to extract messages fromm JSON files if you
have the `PyBabel-json <https://pypi.python.org/pypi/PyBabel-json>`_ package
installed::

     [extension:.json]
     plugin = babel-json

To find out which plugins are available use the ``-list-plugins`` option.

::

    $ bin/pot-create --list-plugins
    python
    xml
    zcml
    

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
  by specifying tne parameter number for both the singular and plural text. For
  example if your function signature is ``show_result(single, plural)`` the
  keyword specifier is ``show_result:1,2``
* If you use message contexts you can specify the parameter used for the context
  by adding a ``c`` to the parameter number. For example the keyword specifier for
  ``pgettext`` is ``pgettext:1c,2``.
* If your function takes the domain as a parameter you can specify which parameter
  is used for the domain by adding a ``d`` to the parameter number. For example
  the keyword specier for ``dgettext`` is ``dgettext:1d,2``. This is a
  lingua-specified extension.
* You can specify the exact number of parameters a function call must have
  using the ``t`` postfix. For example if a funtion *must* have four parameters
  to be a valid call, the specifier could be ``myfunc:1,5t``.


Babel plugin support
--------------------

There are several packages with plugins for `Babel
<http://babel.edgewall.org/>`_'s message extraction tool. Lingua can use those
plugins as well. The plugin names will be prefixed with ``babel-`` to
distinguish them from lingua extractors.


Comparison to other tools
-------------------------

Differences compared to `GNU gettext <https://www.gnu.org/software/gettext/>`_:

* Support for file formats such as Zope Page Templates (popular in
  `Pyramid <http://docs.pylonsproject.org/projects/pyramid/en/latest/>`_,
  `Chameleon <http://chameleon.readthedocs.org/en/latest/>`_,
  `Plone <http://plone.org/>`_ and `Zope <http://www.zope.org>`_).
* Better support for detecting format strings used in Python.
* No direct support for C, C++, Perl, and many other languages. Lingua focues
  on languages commonly used in Python projects, although support for other
  langauges can be added via plugins.


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


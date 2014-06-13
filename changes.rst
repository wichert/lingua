Changelog
=========

2.3 - June 13, 2014
-------------------

- Fix incorrect invocation of legacy Babel extraction plugins. This fixes
  `issue 28 <https://github.com/wichert/lingua/issues/28>`_.

- TAL template handling fixes:

  - Correctly handle `structure:` prefixes in TAL expressions. Patch from
    Ingmar Steen
    (`pull request 32 <https://github.com/wichert/lingua/pull/32>`_).

  - Fix handling of multi-line `tal:content, `tal:define` and `tal:replace`
    statements. Patch from Ingmar Steen
    (pull requests
    `35 <https://github.com/wichert/lingua/pull/35>`_ and
    `36 <https://github.com/wichert/lingua/pull/36>`_).

  - Fix handling of `tal:repeat` statements with multiple assignments. Patch
    from Ingmar Steen
    (`pull request 37 <https://github.com/wichert/lingua/pull/37>`_).


2.2 - June 10, 2014
-------------------

- Remove seconds from POT timestamps. No other tool includes seconds, and this
  appearently breaks Babel.

- Fix Python 2.6 compatibility. Patch from Hugo Branquinho
  (`pull request 25 <https://github.com/wichert/lingua/pull/25>`_).

- Fix installation problems on Python 3. Patch from William Wu
  (`pull request 27 <https://github.com/wichert/lingua/pull/27>`_).

- Handle TALES expression engine selection. This fixes
  `issue 30 <https://github.com/wichert/lingua/issues/30>`_.

- Handle Python expressions using curly braces in HTML templates. This fixes
  `issue 29 <https://github.com/wichert/lingua/issues/29>`_.


2.1 - April 8, 2014
-------------------

- Do not break when encountering HTML entities in Python expressions in XML
  templates.

- Show the correct linenumber in error messages for syntax errors in Python
  expressions occurring in XML templates.

- Fix bug in parsing of ``tal:repeat`` and ``tal:define`` attributes in the
  XML parser.

- Tweak ReST-usage in changelog so the package documentation renders correctly
  on PyPI.


2.0 - April 8, 2014
-------------------

- Lingua is now fully Python 3 compatible.

- Add a new ``pot-create`` command to extract translateable texts. This is
  (almost) a drop-in replacement for GNU gettext's ``xgettext`` command and
  replaces the use of Babel's extraction tools. For backwards compatibility
  this tool can use existing Babel extraction plugins.

- Define a new extraction plugin API which enables several improvements to
  be made:

  - You can now select which domain to extract from files. This is currently
    only supported by the XML and ZCML extractors.
  - Format strings checks are now handled by the extraction plugin instead of
    applied globally. This prevents false positives.
  - Message contexts are fully supported.

- Format string detection has been improved: both C and Python format strings
  are now handled correctly.

- The XML/HTML extractor has been rewritten to use HTML parser from Chameleon_.
  This allows lingua to handle HTML files that are not valid XML.

- Whitespace handling in XML extractor has been improved..

- The po-xls conversion tools have been moved to a new `po-xls
  <https://github.com/wichert/po-xls>`_ package.


1.6 - December 9, 2013
----------------------

- Add support for ngettext and pluralize() for correctly generating plurals in
  pot files.


1.5 - April 1, 2013
-------------------

- Do not silently ignore XML parsing errors. Instead print an error message
  and abort.


1.4 - February 11, 2013
-----------------------

- Po->XLS convertor accidentily included obsolete messages.


1.3 - January 28, 2012
----------------------

- XLS->Po conversion failed for the first language if no comment or
  reference columns were generated. Reported by Rocky Feng.

- Properly support Windows in the xls-po convertors: Windows does not
  support atomic file renames, so revert to shutils.rename on that
  platform. Reported by Rocky Feng.


1.2 - January 13, 2012
----------------------

- Extend XML extractor to check python expressions in templates. This
  fixes `issue 7 <https://github.com/wichert/lingua/pull/7>`_. Thanks to
  Nuno Teixeira for the patch.


1.1 - November 16, 2011
-----------------------

- Set 'i18n' attribute as default prefix where there was no prefix found.
  This fixes issues `5 <https://github.com/wichert/lingua/issues/5>`_ and
  `6 <https://github.com/wichert/lingua/issues/5>`_. Thanks to
  Mathieu Le Marec - Pasquet for the patch.


1.0 - September 8, 2011
-----------------------

- Update XML extractor to ignore elements which only contain a Chameleon
  expression (``${....}``). These can happen to give the template engine
  a hint that it should try to translate the result of an expression. This
  fixes `issue 2 <https://github.com/wichert/lingua/issues/2>`_.

* Update XML extractor to not abort when encountering undeclared
  namespaces. This fixes `issue 3
  <https://github.com/wichert/lingua/issues/3>`_.

* Fix Python extractor to handle strings split over multiple lines
  correctly.


1.0b4 - July 20, 2011
---------------------

* Fix po-to-xls when including multiple languages in a single xls file.


1.0b3 - July 18, 2011
---------------------

* Paper brown bag: remove debug leftover which broke po-to-xls.


1.0b2 - July 18, 2011
---------------------

* Update PO-XLS convertors to allow selection of comments to include in
  the xls files.

* Correct XML extractor to strip leading and trailing white. This fixes
  `issue 1 <https://github.com/wichert/lingua/issues/1>`_.

* Add a very minimal polint tool to perform sanity checks in PO files.

* Update trove data: Python 2.4 is not supported due to lack of absolute
  import ability.


1.0b1 - May 13, 2011
--------------------

* First release.

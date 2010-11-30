mw2moin.py
==========

Convert an entire MediaWiki wiki to a MoinMoin wiki.  Using an XML export
from MediaWiki, a MoinMoin directory with all pages, revisions, attachments,
and active editors will be generated.  You must have the following:

 * Python 2.6+
 * MediaWiki 1.5+ (live)
 * MoinMoin 1.7.1+


License
-------

mw2moin is released under the modified BSD license.  See mw2moin.py
for the full license text.


Usage
-----

First generate the XML export from MediaWiki (the database must be up).

         > cd $MW/maintenance/
         > php dumpBackup.php --full --output=[file].gz

where `$MW` is the base of your MediaWiki installation.  You may want to use
additional filter arguments for the `dumpBackup.php` script; run it without
arguments for more directions.

Unzip the resultant output, then run `mw2moin.py`.

        > ./mw2moin.py out file

which will generate the MoinMoin compatible directory at `$PWD/out/`

        > ./mw2moin.py -n out file

will not translate MediaWiki syntax to MoinMoin syntax in case you want to
use a parser plugin to deal with it.

        > ./mw2moin.py -a $MW/images/ out file

will copy attachments from `$MW/images/` into the generated directory.

        > ./mw2moin.py -b http://example.com/wiki/ out file

will replace any links to the old wiki URL with a wiki link.


Installation
------------

After generating the directory, place it where your config .py will
find it.  Be sure to change the front page to `u'Main Page'` in the
config.  If a local underlay and interwiki map are desired, copy or
move them into the generated directory.

Note that all of the users created for the wiki are enabled but have
no password.

Known Bugs
----------

 * Table headers are not converted correctly all the time.
 * There is no analog for `Image:` pages since attachments in MoinMoin
   are not first class citizens.  They'll be moved over but likely
   orphaned.
 * Macros are not translated.
 * ACLs are not translated.
 * Used on one three-year old wiki, but it probably didn't contain
   the breadth of input that would stress this type of script.

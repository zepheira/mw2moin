#!/usr/bin/env python

"""
     Converts a MediaWiki wiki to a MoinMoin wiki.
     MediaWiki 1.5+
     MoinMoin 1.7.1+
     Ryan Lee (ryanlee@zepheira.com)     

Copyright (c) 2010, Zepheira, LLC
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

 * Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.
 * Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.
 * Neither the name of Zepheira, LLC nor the names of its contributors may
   be used to endorse or promote products derived from this software without
   specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.
"""

import getopt
import os
import sys
import time
import codecs
import re
import shutil
import hashlib

from xml.dom.minidom import parse, parseString
from urllib import quote

DATA_FORMAT = '01070100' 
_DATA_ = None
_USERS_ = {}
_EDIT_LOG_ = {}

def main(argv):
    global _DATA_, _EDIT_LOG_
    try:
        opts, args = getopt.getopt(argv, 'ha:b:n', ["help", "attachments=", "base-url=","no-syntax"])
    except getopt.GetoptError, err:
        print str(err)
        usage()
        sys.exit(2)

    if len(args) != 2:
        print "Expected 2 arguments!"
        usage()
        sys.exit(2)

    wiki     = args[0]
    mwxml    = args[1]
    baseurl  = None
    mwhome   = None
    dosyntax = True
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-a", "--attachments"):
            mwhome = a
        elif o in ("-b", "--base-url"):
            baseurl = a.replace('/','\/').replace('.','\.')
        elif o in ("-n", "--no-syntax"):
            dosyntax = False
        else:
            assert False, "unhandled option"

    _DATA_ = wiki + os.sep + "data"
    _NSMAP_ = {}
    _IGNORE_REVISIONS_ = {}
    
    # directory setup
    plugin_base = _DATA_ + os.sep + "plugin" + os.sep
    os.mkdir(wiki)
    os.mkdir(_DATA_)
    os.mkdir(wiki + os.sep + "underlay")
    os.mkdir(_DATA_ + os.sep + "dict")
    os.mkdir(_DATA_ + os.sep + "pages")
    os.mkdir(_DATA_ + os.sep + "user")
    os.mkdir(_DATA_ + os.sep + "plugin")
    os.mkdir(plugin_base + "action")
    os.mkdir(plugin_base + "converter")
    os.mkdir(plugin_base + "events")
    os.mkdir(plugin_base + "filter")
    os.mkdir(plugin_base + "formatter")
    os.mkdir(plugin_base + "macro")
    os.mkdir(plugin_base + "parser")
    os.mkdir(plugin_base + "theme")
    os.mkdir(plugin_base + "userprefs")
    os.mkdir(plugin_base + "xmlrpc")

    # Python init file setup
    open("%s%s__init__.py" % (plugin_base, os.sep), "w").close()
    makePluginInit("%s%s%s" % (plugin_base, os.sep, "action"))
    makePluginInit("%s%s%s" % (plugin_base, os.sep, "converter"))
    makePluginInit("%s%s%s" % (plugin_base, os.sep, "events"))
    makePluginInit("%s%s%s" % (plugin_base, os.sep, "filter"))
    makePluginInit("%s%s%s" % (plugin_base, os.sep, "formatter"))
    makePluginInit("%s%s%s" % (plugin_base, os.sep, "macro"))
    makePluginInit("%s%s%s" % (plugin_base, os.sep, "parser"))
    makePluginInit("%s%s%s" % (plugin_base, os.sep, "theme"))
    makePluginInit("%s%s%s" % (plugin_base, os.sep, "userprefs"))
    makePluginInit("%s%s%s" % (plugin_base, os.sep, "xmlrpc"))

    # key file setup
    fmeta = open(_DATA_ + os.sep + "meta", "w")
    fmeta.write("data_format_revision: %s\n" % DATA_FORMAT)
    fmeta.close()
    
    fdict = open(_DATA_ + os.sep + "dict" + os.sep + "dummy_dict", "w")
    fdict.write("\n")
    fdict.close()

    # import XML from argv[1]
    dom = parse(mwxml)
    doc = dom.documentElement

    namespaces = doc.getElementsByTagName('namespace')
    for namespace in namespaces:
        key = namespace.getAttribute('key')
        if namespace.firstChild is not None:
            _NSMAP_[key] = namespace.firstChild.nodeValue
        else:
            _NSMAP_[key] = u''
    
    pages = doc.getElementsByTagName('page')
    for page in pages:
        title = page.getElementsByTagName('title')[0].firstChild.nodeValue
        moinPage = getMoinPage(title, baseurl, mwhome, dosyntax)
        revisions = page.getElementsByTagName('revision')
        for revision in revisions:
            rid = revision.getElementsByTagName('id')[0].firstChild.nodeValue
            user = None
            contributor = revision.getElementsByTagName('contributor')[0]
            ips = contributor.getElementsByTagName('ip')
            usernames = contributor.getElementsByTagName('username')
            if ips.length > 0:
                ip = ips[0].firstChild.nodeValue
                if ip == "MediaWiki default":
                    _IGNORE_REVISIONS_[contributor.parentNode.getElementsByTagName('id')[0].firstChild.nodeValue] = True
                    next
                else:
                    user = getMoinUser(ip, ip=True)
            else:
                username = usernames[0].firstChild.nodeValue
                user = getMoinUser(username)
            isotime = revision.getElementsByTagName('timestamp')[0].firstChild.nodeValue
            textEl = revision.getElementsByTagName('text')[0]
            text = ""
            if textEl.firstChild is not None:
                text = textEl.firstChild.nodeValue
            commentEls = revision.getElementsByTagName('comment')
            comment = None
            if len(commentEls) > 0:
                comment = commentEls[0].firstChild.nodeValue
            if (not _IGNORE_REVISIONS_.has_key(rid)):
                moinPage.addRevision(isotime, text, user.moinid, comment)

    elKeys = _EDIT_LOG_.keys()
    elKeys.sort()
    fgel = codecs.open(_DATA_ + os.sep + "edit-log",encoding='utf-8',mode="w")
    for k in elKeys:
        fgel.write(_EDIT_LOG_[k])
    fgel.close()

    # final directions
    print "Depending on your underlay and interwiki settings, you may need to"
    print " Copy MoinMoin install's underlay/* to %s/underlay/" % wiki
    print " Copy MoinMoin install's data/intermap.txt to %s/data/intermap.txt" % wiki
    sys.exit()

class MoinUser():
    def __init__(self, username, ip=False):
        time.sleep(2)
        ts = time.time()
        self.moinid = "%s.%d" % (ts, os.getpid())
        self.username = username
        self.last_saved = ts
        if ip:
            self.disabled = 1
        else:
            self.disabled = 0

def usage():
    print """Usage: %s [-h||--help] [-n||--no-syntax] [-b url|--base-url=url] [-a dir|--attachments=dir] name file
  -h: Print this message
  -n: Leave MediaWiki syntax intact; do not translate
  -b: Substitute instances of the wiki's original URL with a wiki link
  -a: Media directory of the MediaWiki installation to include uploads;
      incompatible with --no-syntax
  name: Directory in which to put the MoinMoin wiki
  file: MediaWiki exported XML

  Generate the MediaWiki exported XML by running 
    > cd $MW/maintenance
    > php dumpBackup.php --full --output=[file].gz

  where $MW is the directory where MediaWiki is installed.
""" % sys.argv[0]

def makePluginInit(dir):
    ifile = open("%s%s__init__.py" % (dir, os.sep), "w")
    ifile.write("""# -*- coding: iso-8859-1 -*-
from MoinMoin.util import pysupport
modules = pysupport.getPackageModules(__file__)
""")
    ifile.close()

def getMoinUser(username, ip=False):
    if _USERS_.has_key(username):
        return _USERS_[username]
    else:
        user = MoinUser(username, ip)
        fuser = codecs.open(_DATA_ + os.sep + "user" + os.sep + user.moinid, encoding='utf-8', mode="w")
        fuser.write("""aliasname=
bookmarks{}=
css_url=
date_fmt=
datetime_fmt=
disabled=%d
edit_on_doubleclick=0
edit_rows=20
editor_default=text
editor_ui=freechoice
email=
email_subscribed_events[]=
enc_password=
jabber_subscribed_events[]=
jid=
language=
last_saved=%s
mailto_author=0
name=%s
quicklinks[]=
real_language=
""" % (user.disabled, user.last_saved, user.username))
        fuser.close()
        _USERS_[username] = user
        return user

def mwTitleToMoinTitle(title):
    """MoinMoin treats the - as a reserved character.  Bad MoinMoin."""
    def lowerquoterepl(obj):
        return "(%s)" % obj.group(0)[1:].lower()
    return re.sub("(%[0-9A-F]{2})", lowerquoterepl, quote(title, safe='').replace(' ','%20')).replace('-', '(2d)').replace('.', '(2e)')

class MoinPage():
    def __init__(self, title, baseurl=None, attachments_dir=None, dosyntax=True):
        self.baseurl = baseurl
        self.attachments_dir = attachments_dir
        self.dosyntax = dosyntax
        self.original_title = title
        self.title = mwTitleToMoinTitle(title)
        self.revisionid = 0
        self.path = _DATA_ + os.sep + "pages" + os.sep + self.title
        self.revisions = self.path + os.sep + "revisions"
        self.attachments = self.path + os.sep + "attachments"
        os.mkdir(self.path)
        os.mkdir(self.revisions)
        os.mkdir(self.attachments)

    def editLog(self, msg):
        mode = "a"
        if (self.revisionid == 1):
            mode = "w"
        fel = codecs.open(self.path + os.sep + "edit-log", encoding='utf-8', mode=mode)
        fel.write("%s" % msg)
        fel.close()

    def updateCurrent(self):
        fcur = open(self.path + os.sep + "current", "w")
        fcur.write("%0.8d\n" % self.revisionid)
        fcur.close()

    def copyAttachments(self, text):
        """
        Find files and copy them over.
        """
        matches = re.compile(r'\{\{attachment:([^ \|\}]+)').findall(text)
        if len(matches) > 0:
            for match in matches:
                hash = hashlib.md5(match.encode('utf-8')).hexdigest()
                imgf = "%s/%s/%s/%s" % (self.attachments_dir, hash[0], hash[0:2], match)
                print imgf
                if os.access(imgf, os.F_OK):
                    shutil.copy(imgf, self.attachments)

    def addRevision(self, isotimestamp, text, username, comment):
        self.revisionid += 1
        editmode = "SAVE"
        if comment is None:
            comment = ""
        if self.revisionid == 1:
            editmode = "SAVENEW"
        frev = codecs.open(self.revisions + os.sep + "%0.8d" % self.revisionid, encoding='utf-8', mode='wb')
        moinSyntax = text
        if self.dosyntax:
            moinSyntax = mwSyntaxToMoinSyntax(text, baseurl=self.baseurl)
        frev.write(moinSyntax)
        frev.close()
        editlog_ts = "%.0f000000" % time.mktime(time.strptime(isotimestamp,"%Y-%m-%dT%H:%M:%SZ"))
        editlog_entry = "%s\t%0.8d\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" % (
            editlog_ts,
            self.revisionid,
            editmode,
            self.title,
            "127.0.0.1",
            "localhost",
            username,
            "",
            comment
            )
        self.editLog(editlog_entry)
        _EDIT_LOG_[editlog_ts] = editlog_entry
        self.updateCurrent()
        if self.dosyntax and self.attachments_dir is not None:
            self.copyAttachments(moinSyntax)

def getMoinPage(title, baseurl, attachments_dir, dosyntax):
    page = MoinPage(title, baseurl=baseurl, attachments_dir=attachments_dir, dosyntax=dosyntax)
    return page

def mwSyntaxToMoinSyntax(text, baseurl=None):
    """
    From MediaWiki to MoinMoin.

    All of the single quote mappings work.
    All of the heading mappings work.
    All of the horizontonal rule mappings work (one maps into one of many).
    All of the internal link mappings work.

    <u>text</u> becomes __text__
    (<pre>|<nowiki>)text(</pre>|</nowiki>) becomes {{{text}}}
    (<s>|<del>)text(</s>|</del>) becomes --(text)--
    '* text' becomes ' * text'
    '** text' becomes '  * text'
    '# text' becomes ' 1. text'
    '## text' becomes '  1. text'
    '#* text' becomes '  * text'
    ': text' beocomes ' text'
    ':: text' becomes '  text'
    ';text\n: text2' becomes 'text:: text2'
    [link text] becomes [[link|text]]
    [[File:embedded|text]] becomes {{attachment:embedded|text}}
    """
    # Maybe do this later
    # {{attachment:<name>_}} bug - kill last space in filename...
    # [[Image:]] making it through...? should be subbed away
    # Make all CamelCass !CamelCase to prevent Moin link conversion
    # Don't do things inside <pre>, like # replacement or <<BR>>
    # <ul><li> replacement
    no_toc = False

    if re.compile(r'#REDIRECT').match(text):
        return text

    # No space-filled lines
    text = re.sub(re.compile(r'^ +$', re.M), r'', text)
    # No trailing space on headers
    text = re.sub(re.compile(r'= +$', re.I|re.M), r'=', text)
    # Mandatory space between header boundaries and contained text
    text = re.sub(re.compile(r'^(=+)\s*([^=]+?)\s*(=+)$', re.M), r'\1 \2 \3', text)
    # Force a line break and indent on space-indented lines
    text = re.sub(re.compile(r'<br ?\/?>', re.I), r'<<BR>>', text)
    text = re.sub(re.compile(r'^ +(.*?)$', re.M), r': \1 <<BR>>', text)
    # Remove table of contents directive, doing that by default
    text = re.sub(re.compile(r'__TOC__', re.I), r'', text)
    # Toggle flag for later use and remove directive
    if re.search(re.compile(r'^__NOTOC__$', re.M), text) is not None:
        no_toc = True
        text = re.sub(re.compile(r'__NOTOC__'), r'', text)
    def link_space_repl(matchobj):
        return matchobj.group(0).replace('_', ' ')
    def file_space_repl(matchobj):
        return matchobj.group(0).replace(' ', '_')
    # Attachments
    text = re.sub(re.compile(r'\[\[Image:(https?:\/\/.*?)\]\]'), r'{{\1}}', text)
    text = re.sub(re.compile(r'\[\[Image:(.*?)\]\]'), r'{{attachment:\1}}', text)
    text = re.sub(re.compile(r'\[\[:Image:(.*?)\]\]'), r'[[attachment:\1]]', text)
    text = re.sub(re.compile(r'\{\{attachment:([^ \|]+)\s+([^\|]+)\}\}'), r'{{attachment:\1|\2}}', text)
    # Link syntax
    text = re.sub(re.compile(r'\[((http|mailto|https|ftp|irc):\S+)\s+([^\]]+)\]', re.I), r'[[\1|\3]]', text)
    text = re.sub(re.compile(r'\[{1,}((http|mailto|https|ftp|irc):.*?)\]{1,}'), r'[[\1]]', text)
    # Remove unnecessary wiki URL prefix if asked for
    if baseurl is not None:
        text = re.sub(re.compile(r'(?<!\[)'+baseurl+r'(.+)\b', re.I), r'[[\1]]', text)
        text = re.sub(re.compile(baseurl+r'(images\/[0-9a-f]\/[0-9a-f]{2}\/)?', re.I), r'', text)
    # Substitute underscores with spaces in page link
    text = re.sub(re.compile(r'\[\[((?!http:|mailto:|https:|ftp:|irc:).*?)(\||\]\])'), link_space_repl, text)
    # Substitute spaces with underscores in attachments
    text = re.sub(re.compile(r'\{\{attachment:[^\|\}]+'), file_space_repl, text)
    # Basic formatting replacements
    text = re.sub(re.compile(r'<hr>', re.I), r'----', text)
    text = re.sub(re.compile(r'<u>(.*?)<\/u>', re.I), r'__\1__', text)
    text = re.sub(re.compile(r'<s>(.*?)<\/s>', re.I), r'--(\1)--', text)
    text = re.sub(re.compile(r'<del>(.*?)<\/del>', re.I), r'--(\1)--', text)
    def listrepl(matchobj):
        listind = matchobj.group(1)
        listtxt = matchobj.group(2)
        replacement = ' ' * len(listind)
        if listind[-1] == '#':
            replacement = "%s%s%s" % (replacement, '1. ', listtxt)
        elif listind[-1] == '*':
            replacement = "%s%s%s" % (replacement, '* ', listtxt)
        else:
            replacement = "%s%s" % (replacement, listtxt)
        return replacement
    # Demarcate space-indented block
    text = re.sub(re.compile(r'(?!<pre>.*?)((?:$.^\: [^\r\n]+)+)(?!.*?<\/pre>)', re.I|re.S|re.M), r'\n{{{#!wiki blue/solid\1\n}}}', text)
    # <dl>
    text = re.sub(re.compile(r'^;(.*?)$', re.I|re.M), r'\1:: ', text)
    # <ul style="list-style: none">, <ul>, <ol>
    text = re.sub(re.compile(r'^([\*\#:]+)(.*)$', re.I|re.M), listrepl, text)
    # indent blockquote
    text = re.sub(re.compile(r'^<blockquote>(.*)<\/blockquote>$', re.I|re.M), r':: \1', text)
    # Formatting that should go at the end
    text = re.sub(re.compile(r'<code>(.*?)<\/code>', re.I), r'`\1`', text)
    text = re.sub(re.compile(r'<b>(.*?)<\/b>', re.I), r"'''\1'''", text)
    text = re.sub(re.compile(r'<pre>(.*?)<\/pre>', re.I|re.S|re.M), r'{{{\1}}}', text)
    text = re.sub(re.compile(r'<nowiki>(.*?)<\/nowiki>', re.I|re.S|re.M), r'{{{\1}}}', text)

    # Table
    # Remove sequential row markings
    text = re.sub(re.compile(r'(?=^\{\|.*?$)(.*?)^ *$.(.*?)(?=^\|\}$)', re.S|re.M), r'\1\2', text)
    # Reformat header rows
    def th_newline_repl(matchobj):
        a = matchobj.group(0)
        a = a.replace('\n', ' !')
        a = a.replace('!!', '||')
        return a[:-1] + "\n"
    text = re.sub(re.compile(r'(^(!.*?)$.)+', re.S|re.M), th_newline_repl, text)
    text = re.sub(re.compile(r'(^\|\-$.)+', re.S|re.M), r'|-\n', text)
    text = re.sub(re.compile(r'^\{\|.*?$', re.I|re.M), r'', text)
    def tr_repl(matchobj):
        a = matchobj.group(1)
        a = re.sub(re.compile(r'^\|-.*?$', re.M), r'', a)
        a = re.sub(re.compile(r'!!'), r'||', a)
        a = re.sub(re.compile(r'^\|', re.M|re.S), r'||', a)
        a = re.sub(re.compile(r'$.^', re.M|re.S), r'', a)
        a = a + " ||\n"
        return a

    def th_repl(matchobj):
        a = matchobj.group(1)
        a = re.sub(re.compile(r'([^|]+?)\|\|'), r"'''\1''' ||", a)
        return "|| " + a

    text = re.sub(re.compile(r'^(!.*?)$', re.M), r'\1 ||', text)
    text = re.sub(re.compile(r'^!(.*?)$', re.M), th_repl, text)
    text = re.sub(re.compile(r'^(\|-.*?)((?=\|-)|(?=\|\}))', re.I|re.S|re.M), tr_repl, text)
    text = re.sub(re.compile(r'^\|\}.*?$', re.I|re.M), r'', text)
    if not no_toc:
        text = "<<TableOfContents(4)>>\n\n%s" % text
    return text

if __name__ == "__main__":
    main(sys.argv[1:])

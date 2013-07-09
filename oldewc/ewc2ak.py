#!/usr/bin/env python
"""
Command-line tool for HTML-ifying EWC texts.
"""

import sys, re, StringIO, logging
import config, utils, dom, namespaces, extensions, parser

def convertFile(inf, outf, hd=0):
    print "Reading..."
    doc = parser.MarkupParser().parse(iter(open(inf)))
    print "\nWriting..."
    open(outf, "w").writelines(doc.visit(dom.KindleDomVisitor(hd)))

#
# End of code.
#

if __name__ == "__main__":
    convertFile("00.txt", "00.html")

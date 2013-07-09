#!/usr/bin/env python
"""
config.py: A module from EWC (http://piclab.com/ewc/).

Configuration variables for various EWC modules and functions.
"""

# Input encoding to assume if unknown
inputEncoding = "ascii"

# Default character encoding for output
outputEncoding = "utf-8"

# URL pattern for links to local pages
localLinkPattern = "/w/%s.html"

# URL pattern for links to local images
localImagePattern = "/images/%s"

# Compact or readable HTML output
compactHTML = False

# Path to find included files: None supresses includes
includePath = None

# Include recursion depth at which to error out
includeDepthLimit = 20

standardURISchemes = (
    u"acap", u"cap", u"cid", u"data", u"dav", u"dict", u"fax",
    u"file", u"ftp", u"http", u"https", u"im", u"imap", u"info", u"ldap", u"mailto",
    u"mid", u"news", u"nfs", u"nntp", u"pop", u"snmp", u"telnet",
)

class ParsingContext(object):
    def __init__(self):
        self.quotesAndDashes = True
        self.emAndStrong = False
        self.nakedURLs = False

        self.namespaceHandlers = {}
        self.extensionHandlers = {}

        self.doc = None

    def addNamespace(self, name, handler):
        assert isinstance(name, unicode)
        self.namespaceHandlers[name] = handler

    def getNamespace(self, name):
        try:
            return self.namespaceHandlers[name]
        except KeyError:
            return self.namespaceHandlers[u""]

    def addExtension(self, name, handler):
        assert isinstance(name, unicode)
        self.extensionHandlers[name] = handler
        
    def getExtension(self, name):
        try:
            return self.extensionHandlers[name]
        except KeyError:
            return self.extensionHandlers[u""]

parsingContext = ParsingContext()

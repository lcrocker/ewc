#!/usr/bin/env python
#
"""
Parser for EWC (see ewc.doc in the docs directory for details).
"""

import sys, re, logging
from xml.sax.saxutils import escape as xmlescape
import xml.etree.ElementTree as etree
from . import namespaces, extensions


class Parser(object):
    """
    The parser object parses an EWC document into an ElementTree.
    From there, one can produce HTML in the usual way, or fiddle
    with it in custom ways.
    """
    def __init__(self, doctitle = "EWC Document", logname = "com.piclab.ewc"):
        self.document_title = doctitle

        self.logger = logging.getLogger(logname)
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("EWC: %(levelname)s %(message)s"))
        self.logger.addHandler(h)
        self.logger.setLevel(logging.ERROR)

        self.namespaces = namespaces.builtins
        self.extensions = extensions.builtins

    def get_logger(self): return self.logger
    def set_logger(self, l): self.logger = l
    def get_link_pattern(self): return self.namespaces[""].get_link_pattern()
    def set_link_pattern(self, p): self.namespaces[""].set_link_pattern(p)
    def get_image_pattern(self): return self.namespaces[""].get_image_pattern()
    def set_image_pattern(self, p): self.namespaces[""].set_image_pattern(p)
    def get_title(self): return self.document_title
    def set_title(self, title): self.document_title = title

    def parse(self, input):
        """
        Produce an element tree from the given input stream.
        """
        root = etree.Element("html")
        h = etree.SubElement(root, "head")
        t = etree.SubElement(h, "title")
        t.text = self.document_title
        body = etree.SubElement(root, "body")

        for line in input:
            p = etree.SubElement(body, "p")
            p.text = line[:-1]

        return root

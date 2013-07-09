#!/usr/bin/env python
"""
Handling EWC (Extended WikiCreole).
See ewc.doc for a detailed explanation of the syntax of EWC itself.
"""

import sys, re, StringIO, logging

# relative imports
import config, utils, dom, namespaces, extensions

def getClosedStyles(line):
    closed_style_pattern = re.compile(u"\\s*<<([#\\.][A-Za-z_][A-Za-z0-9_-]*)>>(.*)$")

    styles = []
    while True:
        m = closed_style_pattern.match(line)
        if m:
            name, tail = m.groups()
            styles.append(name)
            line = tail
        else:
            break
    return styles, line

def applyStyles(styles, node):
    for line in styles:
        if u"#" == line[0]:
            node.attr[u"id"] = line[1:]
        else:
            node.attr.addClass(line[1:])

def blockType(t):
    if u";" == t or u":" == t: return dom.DictionaryList
    elif u"*" == t: return dom.UnorderedList
    elif u"#" == t: return dom.OrderedList
    elif u"|" == t: return dom.Table
    else: return None

def itemType(t):
    if u"#" == t or u"*" == t: return dom.ListItem
    elif u";" == t: return dom.DictionaryTerm
    elif u":" == t: return dom.DictionaryDef
    else: return None

def newLink(content):
    args = content.split(u"|", 1)
    link = args.pop(0)

    if args:
        text = args.pop(0)
    else:
        ns, text = namespaces.getPrefix(link)
    node = dom.Link(addr=namespaces.linkURL(link))
    node.addText(text)
    return node

def newSpan(name, content):
    s = dom.Span()
    applyStyles([name], s)
    s.addText(content)
    return s

def newImage(content):
    args = content.split(u"|")
    src = args.pop(0)

    if args:
        alt = args.pop(0)
    else:
        alt = src

    node = dom.Image(addr=namespaces.imageURL(src))
    node.attr["alt"] = alt

    if args:
        node.attr["width"] = args.pop(0)
    if args:
        node.attr["height"] = args.pop(0)

    return node

def newComment(content):
    return dom.Comment(val=content)

def findSpanOrLink(node):
    """
    Find inline style spans and link markup.
    Spans can be arbitrarily nested, and link text can contain spans,
    but link text cannot contain nested links.
    Yes, this is a lot hairier than a typical parser of such things,
    mainly to maintain the "errorless syntax" restriction, so things
    like missing or mismatched close tags are tolerated.
    """
    open_pattern = re.compile(                  # <<  [[
        u"(.*?)(\\[\\[|<<)(.*)\\Z", re.DOTALL)
    open_or_close_pattern1 = re.compile(        # <<  >>
        u"(.*?)(<<|>>)(.*)\\Z", re.DOTALL)
    open_or_close_pattern2 = re.compile(        # <<  ]]
        u"(.*?)(<<|\\]\\])(.*)\\Z", re.DOTALL)
    open_or_close_pattern3 = re.compile(        # <<  [[  >>
        u"(.*?)(<<|\\[\\[|>>)(.*)\\Z", re.DOTALL)
    style_name_pattern = re.compile(
        u"([#\\.][A-Za-z_][A-Za-z0-9_-]*)\\s*(.*)\\Z")

    m1 = open_pattern.match(node.value)
    if not m1:
        return None, None, None
    pre, firsttag, tail = m1.groups()

    depth = 1
    stack = [firsttag]
    inlink = (u"[[" == firsttag)
    content = u""

    while True:
        if inlink:
            if u"<<" == stack[-1]:
                m2 = open_or_close_pattern1.match(tail)
            else:
                m2 = open_or_close_pattern2.match(tail)
        else:
            m2 = open_or_close_pattern3.match(tail)

        if not m2:
            content += tail
            tail = u""
            break
        else:
            c, tag, tail = m2.groups()
            content += c
            if u">>" == tag or u"]]" == tag:
                stack.pop()
                if not stack:
                    break
                if u"]]" == tag:
                    inlink = False
            else:
                stack.append(tag)
                if u"[[" == tag:
                    inlink = True
            content += tag

    if u"[[" == firsttag:
        node = newLink(content)
    else:
        m = style_name_pattern.match(content)
        if not m:
            name = None
        else:
            name, content = m.groups()
        if not content:
            c = []
            p = list(pre)
            i = 0
            while i < len(tail)-1 and tail[i].isspace():
                p.append(tail[i])
                i += 1
            while i < len(tail)-1 and not tail[i].isspace():
                c.append(tail[i])
                i += 1
            content = u"".join(c)
        node = newSpan(name, content)
    return node, pre, tail

def findSpanShortcut(node):
    span_types = {
        u"#"    :    u".tt",    u"/"    :    u".i",
        u","    :    u".sub",   u"^"    :    u".sup",
        u"_"    :    u".u",     u"*"    :    u".b"
    }
    span_shortcut_pattern = re.compile(u"(.*?)(##|//|,,|\\^\\^|__|\\*\\*)(.*)\\Z", re.DOTALL)

    m = span_shortcut_pattern.match(node.value)
    if not m:
        return None, None, None

    pre, tag, tail = m.groups()
    type = span_types[tag[0]]

    if config.parsingContext.emAndStrong:
        if u"b" == type: type = u".strong"
        elif u"i" == type: type = u".em"

    end = tail.find(tag)
    if -1 == end:
        return None, None, None
    else:
        content = tail[0:end]
        post = tail[end+2:]
    node = newSpan(type, content)
    return node, pre, post

def findImageOrComment(node):
    image_pattern = re.compile(u"(.*?)(\\{\\{)(.*?)(\\}\\})(.*)\\Z", re.DOTALL)

    m = image_pattern.match(node.value)
    if not m:
        return None, None, None

    pre, open, content, close, post = m.groups()
    if content and u"!" == content[0]:
        node = newComment(content[1:])
    else:
        node = newImage(content)
    return node, pre, post

def findNakedURL(node):
    naked_url_pattern = re.compile(u"(.*?)(http|https|ftp|mailto)" \
        "\\:\\/\\/([^\\s]*)(.*)\\Z", re.DOTALL)

    if not config.parsingContext.nakedURLs:
        return None, None, None

    inlink = False
    n = node.parent
    while not isinstance(n, dom.Division):
        if isinstance(n, dom.Link):
            inlink = True
            break
        n = n.parent
    if inlink:
        return None, None, None

    m = naked_url_pattern.match(node.value)
    if not m:
        return None, None, None

    pre, scheme, name, post = m.groups()
    node = newLink(u"".join([scheme, u"://", name, u"|", scheme, u"://", name]))
    return node, pre, post

class MarkupParser(object):
    """
    Parser object for WText. The main entry here is parse(), and the
    other methods here are just utilities for that.
    """
    def __init__(self, logger=None):
        object.__init__(self)
        if logger:
            self.logger = logger
        else:
            logging.getLogger("ewc")
        self.clear_parser_state()

    def clear_parser_state(self):
        self.doc = dom.Document()
        config.parsingContext.doc = self.doc
        self.stack = [dom.Division(self.doc)]
        self.block_type = None
        self.styles = [[], []]
        self.prefix = u""
        self.compatible_table = False

    def apply_styles(self, s, node):
        applyStyles(self.styles[s], node)
        self.styles[s] = []

    def close_to_div(self):
        while not isinstance(self.stack[-1], dom.Division):
            self.stack.pop()
        self.prefix = u""
        self.block_type = None
        self.compatible_table = False

    def close_div(self):
        self.close_to_div()
        if len(self.stack) > 1:
            self.stack.pop()

    def open_div(self, name):
        self.close_to_div()
        d = dom.Division(self.stack[-1])
        self.stack.append(d)
        self.styles[0].append(name)
        self.apply_styles(0, d)
        self.apply_styles(1, d)

    def new_block(self, bt):
        if not bt:
            bt = dom.Paragraph
        self.block_type = bt

        b = bt(self.stack[-1])
        self.stack.append(b)
        return b

    def new_heading(self, line):
        self.close_to_div()
        h = self.new_block(dom.Heading)
        self.apply_styles(0, h)
        self.stack.pop()
        self.block_type = None

        i = 2
        while not ((i > 7) or (i >= len(line)) or (u"=" != line[i])):
            i += 1

        h.setLevel(i - 1)
        h.addText(line[i:].lstrip().rstrip(u"=").rstrip())

    def new_rule(self):
        self.close_to_div()
        r = self.new_block(dom.Rule)
        self.apply_styles(0, r)
        self.stack.pop()
        self.block_type = None

    def add_cells(self, cells):
        for i in xrange(len(cells)):
            cells[i] = cells[i].lstrip().rstrip()

        if isinstance(self.stack[-1], dom.BaseTableData):
            if cells[0]:
                self.stack[-1].addText(cells[0])
            del cells[0]

        for c in cells:
            if isinstance(self.stack[-1], dom.BaseTableData):
                self.stack.pop()

            if c and u"=" == c[0]:
                self.new_block(dom.TableHeading)
                c = c[1:].lstrip()
            else:
                self.new_block(dom.TableData)

            tb = self.stack[-3]
            tr = self.stack[-2]
            row = len(tb) - 1
            col = len(tr) - 1

            rowspan, colspan = False, False
            if c and u"^" == c[0]:
                rowspan = True
                c = c[1:].lstrip()
            elif c and u"<" == c[0]:
                colspan = True
                c = c[1:].lstrip()

            styles, text = getClosedStyles(c)
            applyStyles(styles, self.stack[-1])

            if colspan:
                c = col
                if 0 != c:
                    self.stack[-1].colspan = -1
                    while -1 == tr[c].colspan:
                        c -= 1
                    tr[c].colspan += 1
            if rowspan:
                r = row
                if 0 != r:
                    self.stack[-1].rowspan = -1
                    while -1 == tb[r][col].rowspan:
                        r -= 1
                    tb[r][col].rowspan += 1

            self.stack[-1].addText(text)

    def add_table_line(self, line):
        if isinstance(self.stack[-1], dom.Division):
            t = self.new_block(dom.Table)
            self.apply_styles(1, t)
    
            if not line.startswith(u"||"):
                self.compatible_table = True

        if self.compatible_table:
            while not isinstance(self.stack[-1], dom.Table):
                self.stack.pop()
            r = self.new_block(dom.TableRow)
            self.apply_styles(0, r)
            self.add_cells(line[1:].split(u"|"))
            return

        if line.startswith(u"||"):
            while not isinstance(self.stack[-1], dom.Table):
                self.stack.pop()
            r = self.new_block(dom.TableRow)
            self.apply_styles(0, r)
            line = line[2:]

        self.add_cells(line.split(u"|"))

    def add_list_line(self, prefix, line):
        lpl = len(self.prefix)
        pl = len(prefix)
        common = 0

        if 0 == lpl:
            self.close_to_div()

        while True:
            if common >= lpl or common >= pl:
                break
            if blockType(self.prefix[common]) != blockType(prefix[common]):
                break
            common += 1

        while lpl > common:
            self.stack.pop()
            self.stack.pop()
            lpl -= 1

        if prefix[common:]:
            for t in  prefix[common:]:
                lb = self.new_block(blockType(t))
                self.apply_styles(1, lb)
                ib = self.new_block(itemType(t))
                self.apply_styles(0, ib)
        else:
            self.stack.pop()
            ib = self.new_block(itemType(prefix[-1]))
            self.apply_styles(0, ib)

        styles, line = getClosedStyles(line)
        applyStyles(styles, self.stack[-1])

        self.stack[-1].addText(line)
        self.prefix = prefix

    def add_plain_line(self, line):
        if self.compatible_table:
            self.close_to_div()

        if not self.block_type:
            p = self.new_block(dom.Paragraph)
            self.apply_styles(1, p)
            self.apply_styles(0, p)
        elif issubclass(self.block_type, (dom.Table, dom.TableRow, dom.BaseTableData)):
            self.add_table_line(line)
            return
        self.stack[-1].addText(line)

    def add_line(self, line):
        bt = blockType(line[0])
        if not bt:
            self.add_plain_line(line)
        else:
            if issubclass(bt, dom.BaseList):
                p = []
                for c in line:
                    if c in u"*#:;":
                        p.append(c)
                    else:
                        break
                prefix = u"".join(p)
                line2 = line[len(prefix):]

                if line2 and not line2[0].isspace():
                    self.add_plain_line(line)
                    return

                if self.block_type and not issubclass(self.block_type, (dom.BaseList, dom.BaseListItem)):
                    self.close_to_div()
                self.add_list_line(prefix, line2.lstrip())
            elif issubclass(bt, dom.Table):
                if self.block_type and not issubclass(self.block_type, (dom.Table, dom.TableRow, dom.BaseTableData)):
                    self.close_to_div()
                self.add_table_line(line)
            else:
                assert False

    open_div_pattern = re.compile(u"\\s*<<([#\\.][A-Za-z_][A-Za-z0-9_-]*)$")
    close_div_pattern = re.compile(u"\\s*>>(.*)$")

    def doBlockMarkup(self, source):
        lines = 0
        for line in source:
            lines += 1
            if ((lines % 1000) == 0):
                self.logger.info("%d lines." % lines)

            while True:
                m = MarkupParser.close_div_pattern.match(line)
                if m:
                    self.close_div()
                    line = m.group(1)
                else:
                    break

            self.styles[0], line = getClosedStyles(line)

            m = MarkupParser.open_div_pattern.match(line)
            if m:
                name = m.group(1)
                self.open_div(name)
                line = u""

            if not line:
                self.close_to_div()
                self.styles[1] = self.styles[0]
                self.styles[0] = []
                continue
            elif line.startswith(u"=="):
                self.new_heading(line)
                continue
            elif line.startswith(u"----"):
                self.new_rule()
                continue

            self.add_line(line) # tables and lists and such done here

            self.styles[1] = self.styles[0]
            self.styles[0] = []

        self.logger.info("%d lines." % lines)

    def doInlineMarkup(self, node):
        """
        Walk the tree doing inline markup inside all the Text nodes.
        We traverse in an odd way to accommodate the fact that inline
        markup may split text nodes into spans while the traversal is
        going on.
        """
        for i, n in enumerate(node):
            if not isinstance(n, dom.Text):
                self.doInlineMarkup(n)
            else:
                for func in (findSpanOrLink, findImageOrComment, findSpanShortcut, findNakedURL):
                    while True:
                        new_node, pre, post = func(n)
                        if None is new_node:
                            break
                        else:
                            n.value = pre
                            if post:
                                node.insert(i+1, dom.Text(val=post))
                            node.insert(i+1, new_node)
                    if not n.value:
                        continue

                while True:
                    b = n.value.find(u"\\\\")
                    if -1 == b:
                        break
                    post = n.value[b+2:]
                    n.value = n.value[:b]
                    if post:
                        node.insert(i+1, dom.Text(val=post))
                    node.insert(i+1, dom.Break())

                if config.parsingContext.quotesAndDashes:
                    n.value = utils.quotesAndDashes(n.value)

    def removeEscapes(self, node):
        if not isinstance(node, dom.Text):
            for n in node:
                self.removeEscapes(n)
        else:
            node.value = utils.removeEscapes(node.value)

    def doMagicComments(self, node):
        """
        Traverse the dom tree interpreting "magical" comment nodes.
        Happens after all markup processing.
        """
        if not isinstance(node, dom.Comment):
            for n in node:
                self.doMagicComments(n)
        else:
            pass

    def parse(self, source):
        """
        Create document from input source.
        """
        self.clear_parser_state()

        pass1 = utils.UnicodeTransform(source)
        pass2 = utils.EscapeTransform(iter(pass1))
        pass3 = extensions.ExtensionTransform(iter(pass2))

        self.doBlockMarkup(pass3)

        self.doInlineMarkup(self.doc)
        self.doMagicComments(self.doc)
        self.removeEscapes(self.doc)
        self.doc.normalize()
        return self.doc

def convertString(ins, hd=0):
    """
    >>> import config, utils, dom, namespaces, extensions, parser
    >>> source = open("tests/parser.in").read()
    >>> html = parser.convertString(source)
    >>> res = open("tests/parser.out").read()
    >>> res == html
    True
    """
    source = StringIO.StringIO(ins)
    doc = MarkupParser().parse(source)
    return u"".join(doc.visit(dom.HTMLDomVisitor(hd)))

#
# End of code.
#

if __name__ == "__main__":
    import doctest
    doctest.testmod()

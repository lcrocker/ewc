#!/usr/bin/env python
"""
dom.py: A module from EWC (http://piclab.com/ewc/).

The parser in this package parses EWC into a dom tree structure
which can be output in various formats (though it is certainly
designed with HTML in mind).
The module defines the dom, and contains HTML output functions.
"""

import re
from xml.sax.saxutils import escape as xmlescape, quoteattr as xmlquoteattr

# relative imports
import config
from utils import makeUnicode

class DomError(Exception): pass
class NestingError(DomError): pass
class StyleFormatError(DomError): pass

class Node(object):
    """
    Basic DOM node. Abstract class handles the containment and tree-structure
    stuff; specific node behaviors are handled by concrete subclasses.
    """
    def __init__(self, parent=None):
        if self.__class__ is Node:
            raise NotImplementedError
        object.__init__(self)
        self.allowed_contents = tuple()
        self.children = []

        self.parent = parent
        if parent is not None:
            parent.append(self)

    def _ok_to_add(self, node):
        if isinstance(node, self.allowed_contents):
            node.parent = self
            return node
        else:
            raise NestingError(self, node)

    def __len__(self):
        return len(self.children)
    def __getitem__(self, key):
        return self.children[key]
    def __delitem__(self, key):
        del self.children[key]
    def __setitem__(self, key, child):
        self.children[key] = self._ok_to_add(child)
    def append(self, child):
        self.children.append(self._ok_to_add(child))
    def extend(self, v):
        for c in v: self.append(c)
    def index(self, child, i=0, j=None):
        if j is None: return self.children.index(child, i)
        else: return self.children.index(child, i, j)
    def insert(self, i, child):
        self.children.insert(i, self._ok_to_add(child))
    def pop(self, i=-1):
        return self.children.pop(i)
    def remove(self, node):
        self.children.remove(node)

    def normalize(self):
        """
        Clean up things like adjacent text nodes, empty text nodes,
        whitespace-only nodes in containers like Divisions, Tables, and such,
        and spans with single elements.
        """
        self.children = [c for c in self if not (isinstance(c, Text) and c.isempty())]
        if isinstance(self, (Division, Table, TableRow, BaseList)):
            self.children = [c for c in self if not (isinstance(c, Text) and c.isspace())]

        i = 0
        while True:
            if i >= (len(self) - 1):
                break
            if isinstance(self[i], Text) and isinstance(self[i+1], Text):
                self[i].value += self[i+1].value
                del self[i+1]
            else:
                i += 1

        if isinstance(self, Span) and 1 == len(self) \
        and isinstance(self[0], (Break, Link, Image)):
            __pychecker__ = "no-classattr"
            self.attr.merge(self[0].attr)
            self[0].attr = self.attr
            self.parent[self.parent.index(self)] = self[0]
            __pychecker__ = ""

        for n in self: n.normalize()

    def dump(self, level=0):
        """
        Used for debugging and testing.
        """
        prefix = " _" * level if level else ""
        if isinstance(self, Text):
            __pychecker__ = "no-classattr"
            size = len(self.value)
            __pychecker__ = ""
        else:
            size = len(self)

        if isinstance(self, Element):
            try:
                cl = "[%s]" % self.attr.classval()
            except KeyError:
                cl = "[]"
        else:
            cl = ""

        print prefix, self.__class__.__name__, ("%s (%d)" % (cl, size))
        for n in self:
            n.dump(level+1)

class AttributeMap(object):
    """
    Maintain element attributes. Styles and classes are treated
    specially so that they can be tested separately and aggregated
    reasonably efficiently.  Keys are ASCII text, values are Unicode.
    """
    def __init__(self):
        object.__init__(self)
        self.classes = []
        self.styles = {}
        self.map = {}

    def addClass(self, name):
        if not (self.classes and name in self.classes):
            self.classes.append(name)

    def hasClass(self, name):
        return name in self.classes

    def removeClass(self, name):
        if self.classes and name in self.classes:
            self.classes.remove(name)

    style_pattern = re.compile("\\s*([A-Za-z_][A-Za-z0-9_-]*)\\s*:\\s*(.*)")
    def addStyle(self, style):
        m = self.style_pattern.match(style)
        if not m:
            raise StyleFormatError(style)
        p, v = m.groups()
        v = v.rstrip("; \t\n")
        self.styles[p] = v.decode()

    def hasStyle(self, property):
        return property in self.styles

    def removeStyle(self, property):
        if property in self.styles:
            self.styles.pop(property)

    def merge(self, newmap):
        """
        Merge attributes of another element, overriding ours.
        """
        for c in newmap.classes:
            self.addClass(c)
        self.styles.update(newmap.styles)
        self.map.update(newmap.map)

    def __len__(self):
        n = len(self.map)
        if self.styles: n += 1
        if self.classes: n += 1
        return n

    def classval(self):
        if not self.classes:
            raise KeyError
        return u" ".join(self.classes)

    def styleval(self):
        if not self.styles:
            raise KeyError
        r = []
        for k, v in self.styles.iteritems():
            r.append(u":".join([k.decode(), v]))
        return u";".join(r)

    def __getitem__(self, key):
        if "class" == key: return self.classval()
        elif "style" == key: return self.styleval()
        else: return self.map[key]

    def __delitem__(self, key):
        if "class" == key: self.classes = []
        elif "style" == key: self.styles = []
        else: del self.map[key]

    def __setitem__(self, key, val):
        if "class" == key:
            self.classes = val.split(u" ")
        elif "style" == key:
            styles = val.split(u";")
            for s in styles:
                if not s:
                    continue
                spl = s.split(":", 1)
                if 1 == len(spl):
                    spl.append("")
                self.styles[spl[0].lstrip().rstrip()] = \
                (spl[1].lstrip().rstrip()).decode()
        else:
            self.map[key] = makeUnicode(val)

    def __contains__(self, key):
        if "class" == key: return 0 != len(self.classes)
        elif "style" == key: return 0 != len(self.styles)
        else: return key in self.map

    def clear(self):
        self.classes = []
        self.styles = []
        self.map.clear()

    def items(self):
        r = []
        if self.classes: r.append(("class", self.classval()))
        if self.styles: r.append(("style", self.styleval()))
        r.extend(self.map.items())
        return r

    def keys(self):
        r = []
        if self.classes: r.append("class")
        if self.styles: r.append("style")
        r.extend(self.map.keys())
        return r

    def values(self):
        r = []
        if self.classes: r.append(self.classval())
        if self.styles: r.append(self.styleval())
        r.extend(self.map.values())
        return r

    def _generate_items(self):
        if self.classes: yield ("class", self.classval())
        if self.styles: yield ("style", self.styleval())
        for item in self.map.iteritems():
            yield item

    def iteritems(self):
        return self._generate_items()

    def _generate_keys(self):
        if self.classes: yield "class"
        if self.styles: yield "style"
        for key in self.map.iterkeys():
            yield key
        
    def iterkeys(self):
        return self._generate_keys()

    def _generate_values(self):
        if self.classes: yield self.classval()
        if self.styles: yield self.styleval()
        for val in self.map.itervalues():
            yield val
        
    def itervalues(self):
        return self._generate_values()

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    def setdefault(self, key, default=None):
        try:
            return self.__getitem__(key)
        except KeyError:
            self.__setitem__(key, default)
            return default

    def pop(self, key, default=None):
        try:
            r = self.__getitem__(key)
            self.__delitem__(key)
        except KeyError:
            r = default
        if None is r: raise KeyError
        else: return r

    def popitem(self):
        if self.classes:
            return self.pop("class")
        elif self.styles:
            return self.pop("style")
        else:
            return self.map.popitem()

class CharacterData(Node):
    """
    Carry some common functionality of Text and Comment nodes.
    """
    def __init__(self, parent=None, val=u""):
        if self.__class__ is CharacterData:
            raise NotImplementedError
        Node.__init__(self, parent)
        self._value = makeUnicode(val)

    def isempty(self):
        return 0 == len(self._value)

    def isspace(self):
        return 0 == len(self._value) or self._value.isspace()

    def ispre(self):
        node = self
        while True:
            if isinstance(node, Document):
                return False
            if isinstance(node, Element):
                if node.hasClass("pre") or node.hasClass("code"):
                    return True
                elif node.hasClass("wrap"):
                    return False
            node = node.parent

    def addText(self, text):
        self._value = u"".join([self._value, u"\n", text])

    def _getvalue(self):
        return self._value
    def _setvalue(self, text):
        self._value = makeUnicode(text)
    value = property(_getvalue, _setvalue)

class Text(CharacterData):
    def __init__(self, parent=None, val=u""):
        CharacterData.__init__(self, parent, val)

    def visit(self, visitor):
        return visitor.onText(self)

class Comment(CharacterData):
    def __init__(self, parent=None, val=u""):
        CharacterData.__init__(self, parent, val)

    def visit(self, visitor):
        return visitor.onComment(self)

class Element(Node):
    """
    An Element is a node with attributes.
    Class variables of node types are used only as temporary
    variables for various other code; any permanent attribute
    of a node should be placed in its attributes.
    """
    def __init__(self, parent=None):
        if self.__class__ is Element:
            raise NotImplementedError
        Node.__init__(self, parent)
        self.attr = AttributeMap()

    def visit(self, visitor):
        return visitor.onElement(self)

    def addText(self, text):
        if 0 == len(self) or not isinstance(self[-1], Text):
            Text(self, text)
        else:
            self[-1].addText(text)

class InlineElement(Element):
    def __init__(self, parent=None):
        if self.__class__ is InlineElement:
            raise NotImplementedError
        Element.__init__(self, parent)

    def visit(self, visitor):
        return visitor.onInlineElement(self)

class Span(InlineElement):
    def __init__(self, parent=None):
        InlineElement.__init__(self, parent)
        self.allowed_contents=(CharacterData, InlineElement)

    def visit(self, visitor):
        return visitor.onSpan(self)

class Break(InlineElement):
    def __init__(self, parent=None):
        InlineElement.__init__(self, parent)

    def visit(self, visitor):
        return visitor.onBreak(self)

class Link(InlineElement):
    def __init__(self, parent=None, addr=None):
        InlineElement.__init__(self, parent)
        self.allowed_contents = (CharacterData, Span, Break, Image)
        if addr:
            self.attr["href"] = addr

    def visit(self, visitor):
        return visitor.onLink(self)

class Image(InlineElement):
    def __init__(self, parent=None, addr=None):
        InlineElement.__init__(self, parent)
        if addr:
            self.attr["src"] = addr

    def visit(self, visitor):
        return visitor.onImage(self)

class BlockElement(Element):
    def __init__(self, parent=None):
        if self.__class__ is BlockElement:
            raise NotImplementedError
        Element.__init__(self, parent)

    def visit(self, visitor):
        return visitor.onBlockElement(self)

class Division(BlockElement):
    def __init__(self, parent=None):
        BlockElement.__init__(self, parent)
        self.allowed_contents = (CharacterData, BlockElement, InlineElement)

    def visit(self, visitor):
        return visitor.onDivision(self)

class Paragraph(BlockElement):
    def __init__(self, parent=None, type=None):
        BlockElement.__init__(self, parent)
        self.allowed_contents = (CharacterData, InlineElement)
        if type:
            self.attr["x-type"] = type

    def visit(self, visitor):
        return visitor.onParagraph(self)

class Heading(BlockElement):
    def __init__(self, parent=None, level=1):
        BlockElement.__init__(self, parent)
        self.allowed_contents = (CharacterData, Span, Break)
        self.setLevel(level)

    def setLevel(self, level):
        if level < 1:
            level = 1
        elif level > 6:
            level = 6
        self.attr["x-level"] = unicode(str(level))
        
    def visit(self, visitor):
        return visitor.onHeading(self)

class Rule(BlockElement):
    def __init__(self, parent=None):
        BlockElement.__init__(self, parent)

    def visit(self, visitor):
        return visitor.onRule(self)

class BaseList(BlockElement):
    def __init__(self, parent=None):
        if self.__class__ is BaseList:
            raise NotImplementedError
        BlockElement.__init__(self, parent)
        self.allowed_contents = (CharacterData, ListItem, InlineElement)

    def visit(self, visitor):
        return visitor.onBaseList(self)

class UnorderedList(BaseList):
    def __init__(self, parent=None):
        BaseList.__init__(self, parent)

    def visit(self, visitor):
        return visitor.onUnorderedList(self)

class OrderedList(BaseList):
    def __init__(self, parent=None):
        BaseList.__init__(self, parent)

    def visit(self, visitor):
        return visitor.onOrderedList(self)

class DictionaryList(BaseList):
    def __init__(self, parent=None):
        BaseList.__init__(self, parent)
        self.allowed_contents = (CharacterData, DictionaryTerm, DictionaryDef, InlineElement)

    def visit(self, visitor):
        return visitor.onDictionaryList(self)

class BaseListItem(BlockElement):
    def __init__(self, parent=None):
        if self.__class__ is BaseListItem:
            raise NotImplementedError
        BlockElement.__init__(self, parent)
        self.allowed_contents = (CharacterData, Paragraph, Rule, BaseList, InlineElement)

    def visit(self, visitor):
        return visitor.onBaseListItem(self)

class ListItem(BaseListItem):
    def __init__(self, parent=None):
        BaseListItem.__init__(self, parent)

    def visit(self, visitor):
        return visitor.onListItem(self)

class DictionaryTerm(BaseListItem):
    def __init__(self, parent=None):
        BaseListItem.__init__(self, parent)

    def visit(self, visitor):
        return visitor.onDictionaryTerm(self)

class DictionaryDef(BaseListItem):
    def __init__(self, parent=None):
        BaseListItem.__init__(self, parent)

    def visit(self, visitor):
        return visitor.onDictionaryDef(self)

class Table(BlockElement):
    def __init__(self, parent=None):
        BlockElement.__init__(self, parent)
        self.allowed_contents = (CharacterData, TableRow)

    def visit(self, visitor):
        return visitor.onTable(self)

class TableRow(BlockElement):
    def __init__(self, parent=None):
        BlockElement.__init__(self, parent)
        self.allowed_contents = (CharacterData, BaseTableData)

    def visit(self, visitor):
        return visitor.onTableRow(self)

class BaseTableData(BlockElement):
    def __init__(self, parent=None):
        if self.__class__ is BlockElement:
            raise NotImplementedError
        BlockElement.__init__(self, parent)
        self.allowed_contents = (CharacterData, Paragraph, InlineElement, BaseList)
        self.rowspan = 0
        self.colspan = 0

    def visit(self, visitor):
        return visitor.onBaseTableData(self)

class TableData(BaseTableData):
    def __init__(self, parent=None):
        BaseTableData.__init__(self, parent)

    def visit(self, visitor):
        return visitor.onTableData(self)

class TableHeading(BaseTableData):
    def __init__(self, parent=None):
        BaseTableData.__init__(self, parent)

    def visit(self, visitor):
        return visitor.onTableHeading(self)

class Document(Element):
    """
    Top-level node. Should contain exactly one Division element.
    """
    def __init__(self, parent=None):
        Element.__init__(self, parent)
        self.allowed_contents = (CharacterData, Division)

    def __setitem__(self, key, child):
        if isinstance(child, Division):
            assert 0 == key
            self[0] = self._ok_to_add(child)

    def append(self, child):
        if isinstance(child, Division):
            if self.children:
                self[0] = self._ok_to_add(child)
            else:
                self.children.append(self._ok_to_add(child))

    def insert(self, i, child):
        if isinstance(child, Division):
            assert 0 == i
            self[0] = self._ok_to_add(child)

    def visit(self, visitor):
        return visitor.onDocument(self)

class DomVisitor(object):
    """
    Abstract class for DOM visitors.  At a minimum, one must
    implement onNode(), and everything else will fall through
    to that.  But you can implement different methods for various
    types of nodes or their abstract superclasses.
    """
    def __init__(self):
        if self.__class__ is DomVisitor:
            raise NotImplementedError
        object.__init__(self)

    def onNode(self, n):
        raise NotImplementedError
    def onText(self, n):
        return self.onNode(n)
    def onComment(self, n):
        return self.onNode(n)
    def onElement(self, n):
        return self.onNode(n)
    def onInlineElement(self, n):
        return self.onElement(n)
    def onSpan(self, n):
        return self.onInlineElement(n)
    def onBreak(self, n):
        return self.onInlineElement(n)
    def onLink(self, n):
        return self.onInlineElement(n)
    def onImage(self, n):
        return self.onInlineElement(n)
    def onBlockElement(self, n):
        return self.onElement(n)
    def onDivision(self, n):
        return self.onBlockElement(n)
    def onParagraph(self, n):
        return self.onBlockElement(n)
    def onHeading(self, n):
        return self.onBlockElement(n)
    def onRule(self, n):
        return self.onBlockElement(n)
    def onBaseList(self, n):
        return self.onBlockElement(n)
    def onUnorderedList(self, n):
        return self.onBaseList(n)
    def onOrderedList(self, n):
        return self.onBaseList(n)
    def onDictionaryList(self, n):
        return self.onBaseList(n)
    def onBaseListItem(self, n):
        return self.onBlockElement(n)
    def onListItem(self, n):
        return self.onBaseListItem(n)
    def onDictionaryTerm(self, n):
        return self.onBaseListItem(n)
    def onDictionaryDef(self, n):
        return self.onBaseListItem(n)
    def onTable(self, n):
        return self.onBlockElement(n)
    def onTableRow(self, n):
        return self.onBlockElement(n)
    def onBaseTableData(self, n):
        return self.onBlockElement(n)
    def onTableData(self, n):
        return self.onBaseTableData(n)
    def onTableHeading(self, n):
        return self.onBaseTableData(n)
    def onDocument(self, n):
        return self.onElement(n)


class HTMLDomVisitor(DomVisitor):
    """
    Concrete DomVisitor class for generating HTML4 from a dom tree.
    """
    magic_span_types = ( u"em", u"strong", u"b", u"i", u"tt", u"sub", u"sup", u"abbr", u"acronym", u"dfn", )
    magic_paragraph_types = ( u"blockquote", )

    chars_to_entities = {}
    entities_to_chars = {}
    for _t in ( (0x00A0, u"nbsp"),     (0x2013, u"ndash"),    (0x2014, u"mdash"),
                (0x2018, u"lsquo"),    (0x2019, u"rsquo"),    (0x201C, u"ldquo"),
                (0x201D, u"rdquo"), ):
        chars_to_entities[unichr(_t[0])] = u"".join([u"&", _t[1], u";"])
        entities_to_chars[_t[1]] = _t[0]

    def __init__(self, hd=0, enc=None):
        DomVisitor.__init__(self)
        if hd is None:
            self.heading_depth = 0
        else:
            self.heading_depth = hd
        if enc is None:
            self.encoding = config.outputEncoding

    def onNode(self, e):
        raise NotImplementedError

    def onText(self, e):
        yield xmlescape(e.value, HTMLDomVisitor.chars_to_entities).encode(self.encoding)

    def onComment(self, e):
        yield (u"".join([u"<!--", e.value, u"-->"])).encode(self.encoding)

    def _open_tag(self, e, name, extra_attrs=None):
        if (not config.compactHTML) or (name in { u"p":0, u"div":0, u"h1":0, u"h2":0, u"h3":0, u"h4":0, u"h5":0, u"h6":0, u"ul":0, u"ol":0, u"dl":0, u"li":0, u"br":0, u"hr":0 }):
            tag = [u"\n<", name]
        else:
            tag = [u"<", name]

        for n, v in e.attr.iteritems():
            if n.startswith("x-"):
                continue
            tag.extend([u" ", n, u"=", xmlquoteattr(v)])

        if extra_attrs:
            for n, v in extra_attrs.iteritems():
                tag.extend([u" ", n, u"=", xmlquoteattr(v)])

        if 0 == len(e):
            tag.append(u" />")
        else:
            tag.append(u">")
        return (u"".join(tag)).encode(self.encoding)

    def _do_element(self, e, name, extra_attrs=None):
        yield self._open_tag(e, name, extra_attrs)

        for child in e:
            for line in child.visit(self):
                yield line

        if 0 != len(e):
            yield (u"".join([u"</", name, u">"])).encode(self.encoding)

    def _do_special_element(self, e, name, classes):
        found_special = False
        for t in classes:
            if e.attr.hasClass(t):
                name = t
                e.attr.removeClass(t)
                found_special = True
                break

        yield self._open_tag(e, name)
        if found_special:
            e.attr.addClass(name)
        
        for child in e:
            for line in child.visit(self):
                yield line

        if 0 != len(e):
            yield (u"".join([u"</", name, u">"])).encode(self.encoding)

    def onSpan(self, e):
        return self._do_special_element(e, u"span", HTMLDomVisitor.magic_span_types)

    def onParagraph(self, e):
        return self._do_special_element(e, u"p", HTMLDomVisitor.magic_paragraph_types)

    def _do_base_table_data(self, e, name):
        if -1 == e.rowspan or -1 == e.colspan:
            return u""

        ea = {}
        if e.colspan > 0:
            ea["colspan"] = unicode(e.colspan + 1)
        if e.rowspan > 0:
            ea["rowspan"] = unicode(e.rowspan + 1)
        return self._do_element(e, name, ea)

    def onTableData(self, e):
        return self._do_base_table_data(e, u"td")

    def onTableHeading(self, e):
        return self._do_base_table_data(e, u"th")

    def onHeading(self, e):
        level = int(e.attr.get("x-level", u"2"))
        return self._do_element(e, u"h%d" % (level + self.heading_depth))

    def onImage(self, e):
        if not "alt" in e.attr:
            e.attr["alt"] = u""
        return self._do_element(e, u"img")

    def onLink(self, e):
        return self._do_element(e, u"a")
    def onRule(self, e):
        return self._do_element(e, u"hr")
    def onDivision(self, e):
        return self._do_element(e, u"div")
    def onBreak(self, e):
        return self._do_element(e, u"br")
    def onTable(self, e):
        return self._do_element(e, u"table")
    def onTableRow(self, e):
        return self._do_element(e, u"tr")
    def onOrderedList(self, e):
        return self._do_element(e, u"ol")
    def onUnorderedList(self, e):
        return self._do_element(e, u"ul")
    def onDictionaryList(self, e):
        return self._do_element(e, u"dl")
    def onListItem(self, e):
        return self._do_element(e, u"li")
    def onDictionaryTerm(self, e):
        return self._do_element(e, u"dt")
    def onDictionaryDef(self, e):
        return self._do_element(e, u"dd")
    def onDocument(self, e):
        for line in e[0].visit(self):
            yield line

# End of code

if __name__ == "__main__":
    import doctest
    doctest.testfile("tests/dom.in")

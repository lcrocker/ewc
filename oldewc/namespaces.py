#!/usr/bin/env python
"""
namespaces.py: A module from EWC (http://piclab.com/ewc/).

Handling hypertext link and image namespaces.
Most users will just want to change the paths in the Local namespace
by assigning them in config.py.
"""

import md5

# relative imports
import config
from utils import makeUnicode, removeEscapes

def getPrefix(line):
    """
    If line begins with a colon-separated namespace prefix, return it
    and remove it for further processing.
    
    >>> from namespaces import getPrefix
    >>> getPrefix("")
    (u'', u'')
    >>> getPrefix(":")
    (u'', u'')
    >>> getPrefix(":abc")
    (u'', u'abc')
    >>> getPrefix("::abc")
    (u'', u':abc')
    >>> getPrefix("abc")
    (u'', u'abc')
    >>> getPrefix("abc:")
    (u'abc', u'')
    >>> getPrefix("abc:def")
    (u'abc', u'def')
    >>> getPrefix("abc:def:ghi")
    (u'abc', u'def:ghi')
    >>> getPrefix("abc::")
    (u'abc', u':')
    """
    line = makeUnicode(line.lstrip())

    if not line:
        return u"", line
    if u":" == line[0]:
        return u"", line[1:]
    if not line[0].isalpha():
        return u"", line

    ns = [line[0]]
    i = 1
    while True:
        if i >= len(line):
            return u"", line
        if u":" == line[i]:
            return u"".join(ns), line[i+1:]
        elif (line[i].isalnum()) or (line[i] in u"-_"):
            ns.append(line[i])
        else:
            return u"", line
        i += 1

def linkURL(name, pc=None):
    """
    Given link text with a possible colon-separated namespace prefix,
    return a complete URL for a link.
    """
    name = removeEscapes(name).lstrip().rstrip()
    if u"/" == name[0] or u"#" == name[0]:
        return name

    ns, tail = getPrefix(name)
    if ns:
        if ns in config.standardURISchemes:
            return name
        else:
            return config.parsingContext.getNamespace(ns).linkURL(tail)
    return config.parsingContext.getNamespace(u"").linkURL(tail)

def imageURL(name, pc=None):
    """
    Given link text with a possible colon-separated namespace prefix,
    return a complete URL for an image.
    """
    name = removeEscapes(name).lstrip().rstrip()
    if u"/" == name[0]:
        return name

    ns, tail = getPrefix(name)
    if ns:
        if ns in config.standardURISchemes:
            iu = name
        else:
            iu = config.parsingContext.getNamespace(ns).imageURL(tail)
    iu = config.parsingContext.getNamespace(u"").imageURL(tail)

    if iu is None:
        return u""      # Link to local error image?
    else:
        return iu

class Namespace(object):
    """
    Abstract base class for external namespace handlers.
    """
    def __init__(self):
        if self.__class__ is Namespace:
            raise NotImplementedError
        object.__init__(self)

    def linkURL(self, name):
        raise NotImplementedError

    def imageURL(self, name):
        raise NotImplementedError

class Local(Namespace):
    """
    Namespace for unadorned links.

    >>> import namespaces
    >>> ns = Local()
    >>> ns.linkURL("A Page Title")
    u'/w/a_page_title.html'
    >>> ns.imageURL("imagename.png")
    u'/images/imagename.png'
    """
    def __init__(self):
        Namespace.__init__(self)

    @staticmethod
    def normalize(name):
        """
        Normalize a page name's case, spaces, and such, but do not
        encode any special characters--this must be a repeatable transform,
        having no effect on a name already normalized.  This is done to
        names that should already be mangled for use as URLs so that they
        will map to the same database key and such.  The mangle function
        below should be used on human-readable names.
        """
        return removeEscapes(makeUnicode(name).lstrip().rstrip().lower().replace(u" ", u"_"))

    @staticmethod
    def mangle(title):
        """
        Convert readable page title into something more suitable for an URL.
        We use "$" as the escaping character because Apache gets in our way
        when we use anything it mangles. This is not (nor is it meant to be)
        a reversible tranformation.

        >>> from utils import makeUnicode, removeEscapes
        >>> import namespaces
        >>> namespaces.Local.mangle("A Page Title")
        u'a_page_title'
        >>> namespaces.Local.mangle("2: A 10% $5 B_C")
        u'2$3a_a_10$25_$245_b_c'
        """
        title = Local.normalize(title)
        result = []

        for c in title:
            if c in u"\t\n:\"'%&?<>[]{}*+\\/`~;:@=|$":
                result.append(u"$")
                result.append((u"0"+hex(ord(c))[2:])[-2:])
            else:
                result.append(c)
        return u"".join(result)

    @staticmethod
    def demangle(name):
        """
        Given a name mangled as above, render it in a more readable form.

        >>> from utils import makeUnicode, removeEscapes
        >>> import namespaces
        >>> namespaces.Local.demangle("a_page_title")
        u'A page title'
        >>> namespaces.Local.demangle("2$3a_a_10$25_$245_b_c")
        u'2: a 10% $5 b c'
        """
        v = list(makeUnicode(name))
        for i in xrange(len(name)):
            if v[i] == u"_":
                v[i] = u" "
            elif v[i] == u"$" and i < len(name)-2:
                v[i] = unichr(16 * int(v[i+1], 16) + int(v[i+2], 16))
                v[i+1] = u"\u0000"
                v[i+2] = u"\u0000"
        s = u"".join(v)
        s = removeEscapes(s)
        return s.capitalize()

    def linkURL(self, title):
        return makeUnicode(config.localLinkPattern) % Local.mangle(title)

    def imageURL(self, title):
        return makeUnicode(config.localImagePattern) % Local.mangle(title)

class Wikipedia(Namespace):
    """
    Namespace for Wikipedia links.

    >>> import namespaces
    >>> ns = Wikipedia()
    >>> ns.linkURL("A Page Title")
    u'http://en.wikipedia.org/wiki/A_Page_Title'
    >>> ns.imageURL("imagename.png")
    u'http://upload.wikimedia.org/wikipedia/en/8/89/Imagename.png'
    """
    def __init__(self):
        Namespace.__init__(self)

    @staticmethod
    def mangle(title):
        r = [title[0].upper()]
        for c in title[1:]:
            if u" " == c:
                r.append(u"_")
            elif c in u"%&?<>()[]{}*+\\/`~;:@=":
                r.append(u"%")
                r.append((u"0"+hex(ord(c))[2:])[-2:])
            else:
                r.append(c)
        return u"".join(r)

    def linkURL(self, name):
        ns, tail = getPrefix(name)
        if not ns:
            ns = u"en"
        path = u"http://%s.wikipedia.org/wiki/" % ns
        return u"".join([path, Wikipedia.mangle(tail)])

    def imageURL(self, name):
        ns, tail = getPrefix(name)
        if not ns:
            ns = u"en"
        path = u"http://upload.wikimedia.org/wikipedia/%s/" % ns
        name = Wikipedia.mangle(tail)

        h = md5.new(Wikipedia.mangle(name).encode())
        d = h.hexdigest()
        return u"".join([path, d[0:1], u"/", d[0:2], u"/", name])

class Google(Namespace):
    def __init__(self):
        Namespace.__init__(self)

    @staticmethod
    def mangle(name):
        r = []
        for c in name:
            if u" " == c:
                r.append(u"+")
            elif c in u"%&?<>()[]{}*+\\/`~;:@=":
                r.append(u"%")
                r.append((u"0"+hex(ord(c))[2:])[-2:])
            else:
                r.append(c)
        return u"".join(r)

    def linkURL(self, name):
        return u"http://www.google.com/search?hl=en&q=%s" % Google.mangle(name)

    def imageURL(self, name):
        return None

class Dictionary(Namespace):
    def __init__(self):
        Namespace.__init__(self)

    def linkURL(self, name):
        return u"http://freedictionary.org/?Query=%s&button=Search" % name

    def imageURL(self, name):
        return None

config.parsingContext.addNamespace(u"", Local())
config.parsingContext.addNamespace(u"wp", Wikipedia())
config.parsingContext.addNamespace(u"g", Google())
config.parsingContext.addNamespace(u"d", Dictionary())

# End of code

if __name__ == "__main__":
    import doctest
    doctest.testmod()

#!/usr/bin/env python
"""
utils.py: A module from EWC (http://piclab.com/ewc/).

General utilities for EWC that are used by the parser and may be
handy for things like user-written extensions.
"""

import sys

def makeUnicode(ins):
    """
    Make a string unicode unless it is already.
    Assume default encoding.

    >>> from utils import makeUnicode
    >>> makeUnicode("abc")
    u'abc'
    >>> makeUnicode(u"abc")
    u'abc'
    """
    if isinstance(ins, unicode):
        return ins
    else:
        return ins.decode()

class UnicodeTransform(object):
    """
    Wrap a line iterator (such as an open file) to convert to Unicode.
    
    >>> import utils
    >>> source = iter(["abc","def","ghi"])
    >>> u = UnicodeTransform(source)
    >>> for line in u: print repr(line)
    u'abc'
    u'def'
    u'ghi'
    """
    def __init__(self, source):
        object.__init__(self)
        self.source = source
        self.encoding = None
        self.lines = 0

        try:
            self.encoding = self.source.encoding
        except AttributeError:
            pass
        if not self.encoding:
            self.encoding = sys.getdefaultencoding()

    def __iter__(self):
        return self.main_generator()

    def main_generator(self):
        for line in self.source:
            self.lines += 1
            if not (self.lines % 100):
                print "\r%d lines." % self.lines,
                sys.stdout.flush()
            yield line.decode(self.encoding, "ignore")

def tildeEscapes(ins):
    """
    Implement tilde escapes by shifting the escaped characters by 0xEF00,
    moving them into the Unicode private use area.
    They'll be shifted back after all further processing.
    """
    assert isinstance(ins, unicode)
    v = list(ins)

    i = 0
    while True:
        if i == len(v) - 1:
            if u"~" == v[i]:
                v[i] = u"\u00A0"
                break
        if i > len(v) - 1:
            break
        if u"~" == v[i]:
            v[i] = unichr(0xEF00 + ord(v[i+1]))
            if u"-" == v[i+1]:
                v[i+1] = u"~"
            else:
                del v[i+1]
        i += 1
    return u"".join(v)

class EscapeTransform(object):
    """
    Wrap a source iterator to process tilde escapes,
    space stripping, and line continuations.

    >>> import utils, string
    >>> source = iter(UnicodeTransform(open("tests/escapes.in")))
    >>> res = map(string.rstrip, iter(open("tests/escapes.out").readlines()))
    >>> esc = map(repr, iter(utils.EscapeTransform(source)))
    >>> res == esc
    True
    """
    def __init__(self, source):
        object.__init__(self)
        self.source = source
        self.encoding = None
        try:
            self.encoding = self.source.encoding
        except AttributeError:
            pass
        if not self.encoding:
            self.encoding = sys.getdefaultencoding()

    def __iter__(self):
        return self.main_generator()

    def main_generator(self):
        previous = None
        for line in self.source:
            line = tildeEscapes(line.rstrip())

            if previous is not None:
                line = previous + line
                previous = None

            n = -1
            try:
                while u"\\" == line[n]:
                    n -= 1
            except IndexError:
                pass

            if not (n & 1):
                previous = line[:-1]
            else:
                yield line

        if previous is not None:
            yield previous

def removeEscapes(ins):
    """
    Convert escaped string back to normal, and remove unused codes.

    >>> import utils
    >>> utils.removeEscapes(u"A\uEF42C\u0008D\u0081E\uEF46G")
    u'ABCDEFG'
    """
    removables = map(unichr, (range(0x00,0x09) + range(0x0B,0x20) + range(0x7F,0xA0)))

    assert isinstance(ins, unicode)
    v = list(ins)
    for i in xrange(len(v)):
        if 0xEF00 <= ord(v[i]) <= 0xEFFF:
            v[i] = unichr(ord(v[i]) - 0xEF00)
    return u"".join([c for c in v if not c in removables])

def quotesAndDashes(ins):
    """
    Implement "smart" curly quotes and real dashes.
    
    >>> import utils
    >>> utils.quotesAndDashes(u'A "quote" with---an em dash.')
    u'A \u201cquote\u201d with\u2014an em dash.'
    >>> utils.quotesAndDashes(u"Another 'quote' with 0--1 en dash.")
    u'Another \u2018quote\u2019 with 0\u20131 en dash.'
    >>> utils.quotesAndDashes(u"You're apostropes aren't quotes.")
    u"You're apostropes aren't quotes."
    """
    can_precede = list(u" \t\n\u00A0(\u201C\u2018\u2014")
    can_follow = list(u" \t\n\u00A0):;'\",.?!\u201D\u2019\u2014")

    assert isinstance(ins, unicode)
    if not ins:
        return ins

    v = list(ins)
    v.insert(0, u" ")
    v.append(u" ")

    converted_endash = False
    for i in xrange(1, len(v)-1):
        pre = v[i-1]
        if u"-" == v[i]:
            if u"\uEF2D" == pre:
                v[i] = u"\uEF2D"
            elif u"-" == pre:
                v[i-1] = u"\u0000"
                v[i] = u"\u2013" # En dash
                converted_endash = True
            elif u"\u2013" == pre:
                if converted_endash:
                    v[i-1] = u"\u0000"
                    v[i] = u"\u2014" # Em dash
                    converted_endash = False
            continue

        post = v[i+1]
        if u"\"" == v[i]:
            if pre in can_precede and not post.isspace():
                v[i] = u"\u201C" # Left double quote
            elif post in can_follow and not pre.isspace():
                v[i] = u"\u201D" # Right double quote
        elif u"'" == v[i]:
            if pre in can_precede and not post.isspace():
                v[i] = u"\u2018" # Left single quote
            elif post in can_follow and not pre.isspace():
                v[i] = u"\u2019" # Right single quote

    return u"".join([c for c in v[1:-1] if not u"\u0000" == c])

# End of code

if __name__ == "__main__":
    import doctest
    doctest.testmod()

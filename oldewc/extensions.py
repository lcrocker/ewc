#!/usr/bin/env python
"""
extensions.py: A module from EWC (http://piclab.com/ewc/).

Handling extensions to WikiCreole.
"""

import sys, re
from os.path import join as pathjoin

# relative imports
import config
from utils import EscapeTransform

class Extension(object):
    """
    Abstract base class for EWC extensions.
    To write an extension, subclass this, implement transform(),
    and register the name (see examples like Raw, below).
    """
    def __init__(self):
        if self.__class__ is Extension:
            raise NotImplementedError
        object.__init__(self)

    def transform(self, line, block):
        raise NotImplementedError

    def inline(self, contents):
        return self.transform(contents, None)

    def block(self, contents, source, end_pattern):
        tail = u""
        block = []
        for line in source:
            if line.startswith(end_pattern):
                tail = line[len(end_pattern):]
                break
            else:
                block.append(line)
        result = self.transform(contents, block)
        return result, tail

class Default(Extension):
    """
    Default extension for names not found.
    
    >>> import extensions
    >>> e = DefaultExtension()
    """
    def __init__(self):
        Extension.__init__(self)

    def transform(self, line, block):
        if block:
            yield u"(BLOCK: %s)" % line
            for line in block: yield line
            yield u"(END)"
        else :
            yield u"(INLINE: %s)" % line

class ExtensionTransform(object):
    """
    Create a wrapper around a source iterator that extracts
    and processes extension markup.  I love generators :-)
    """
    raw_pattern = re.compile(u"(.*?)\\{\\{\\{(.*)$")
    ext_pattern = re.compile(u"(.*?)<<(!|[A-Za-z_][A-Za-z0-9_-]*)(.*)$")

    def __init__(self, source):
        object.__init__(self)
        self.stack = [source]

    def __iter__(self):
        return self.main_generator()

    def stack_lines(self):
        while True:
            if 0 == len(self.stack):
                raise StopIteration
            try:
                line = self.stack[-1].next()
            except StopIteration:
                self.stack.pop()
                continue
            else:
                yield line

    def look_ahead(self, source, head="", tail=""):
        """
        Combine the first and last lines of an iterator with the
        head and tail strings passed in. This is used to supress
        the creation of extra newlines in inline extensions such
        as <<include>>.  Traditional parsers wouldn't have to
        do this because they iterate over characters, not lines.
        """
        buf = head
        first = True

        for line in source:
            if first:
                first = False
                buf += line
                continue
            yield buf
            buf = line
        yield buf + tail

    def main_generator(self):
        source = self.stack_lines()
        for line in source:
            m1 = ExtensionTransform.raw_pattern.match(line)
            if m1:
                head, content = m1.groups()
                name = u"raw"
                end_pattern = u"}}}"
            else:
                m2 = ExtensionTransform.ext_pattern.match(line)
                if m2:
                    head, name, content = m2.groups()
                    if u"!" == name:
                        name = u"comment"
                    end_pattern = u">>"
                else:
                    yield line
                    continue

            content = content.lstrip()
            end = content.find(end_pattern)
            ext = config.parsingContext.getExtension(name)

            if -1 == end:
                result, tail = ext.block(content, source, end_pattern)
            else:
                tail = content[end+len(end_pattern):]
                result = ext.inline(content[:end])

            if len(self.stack) > config.includeDepthLimit:
                raise MemoryError("Exceeded input stack depth limit (probably recursion problem)")
            self.stack.append(self.look_ahead(result, head, tail))
#
# A few functions handy for use in extensions here.
#
def token(ins):
    """
    Tokenizer for parsing simple name=value pairs.
    """
    # TODO: \xFF, \u00FF, etc.
    varname_chars = [unichr(c) for c in xrange(sys.maxunicode) if unichr(c).isalnum()]
    varname_chars.extend(u"-_.")

    ins = ins.lstrip()
    if not ins:
        return u"", u""

    f = ins[0]
    if f.isalpha():
        result = [f]
        i = 1
        while i < len(ins) and ins[i] in varname_chars:
            result.append(ins[i])
            i += 1
        return u"".join(result), ins[i:].lstrip()
    elif (u"'" == f or u"\"" == f):
        result = []
        slashmode = False
        i = 1
        while True:
            if i >= len(ins):
                return u"".join(result), u""

            if slashmode:
                if u"t" == ins[i]:
                    result.append(u"\t")
                elif u"n" == ins[i]:
                    result.append(u"\n")
                else:
                    result.append(ins[i])
                slashmode = False
            else:
                if u"\\" == ins[i]:
                    slashmode = True
                elif f == ins[i]:
                    return u"".join(result), ins[i+1:].lstrip()
                else:
                    result.append(ins[i])
            i += 1
    else:
        return f, ins[1:]

def variableAssignments(line):
    """
    Parse name=value pairs on an input line, returning a list
    of tuples (or None if a blank line).
    """
    assert isinstance(line, unicode)
    v = []

    name = None
    while True:
        if not name:
            name, line = token(line)
        if not name:
            break

        t, line = token(line)
        if u"=" == t:
            val, line = token(line)
            v.append((name, val))
            name = None
        else:
            v.append((name, u""))
            name = t
    return v

def variableSubstitutions(source, vars):
    """
    Wrap an iterator replacing variable references like $$this$$
    with their values from the given map.  Used by IncludeFile.
    """
    var_pattern = re.compile(u"(.*?)\\$\\$(.+?)\\$\\$(.*)$")

    for line in source:
        while True:
            m = var_pattern.match(line)
            if not m:
                break
            pre, name, post = m.groups()
            if name in vars:
                line = u"".join( [pre, vars[name], post] )
            else:
                line = u"".join( [pre, u"\uEF24\uEF24", name, u"\uEF24\uEF24", post] )
        yield line

#
# Below here are the built-in extensions themselves:
#
class Comment(Extension):
    """
    Removes its contents from the document entirely.
    """
    def __init__(self):
        Extension.__init__(self)

    __pychecker__ = "no-argsused"
    def transform(self, contents, block):
        yield u""
    __pychecker__ = ""

class EscapeText(Extension):
    """
    Escape everything that might possibly be a markup character.
    They'll be translated back in the last pass of the WText parser.
    """
    def __init__(self):
        Extension.__init__(self)

    def _escape(self, str):
        v = list(str)
        for i in xrange(len(v)):
            if v[i] in u"\\~-\"'=|*#:;/^_,${}[]<>":
                v[i] = unichr(0xEF00 + ord(v[i]))
        return u"".join(v)

    def transform(self, contents, block):
        if contents:
            yield self._escape(contents)
        if block:
            for line in block:
                yield self._escape(line)

class IncludeFile(Extension):
    def __init__(self):
        Extension.__init__(self)
        self.vars = {}

    def error(self, msg):
        yield u"(ERROR: IncludeFile: %s)" % msg

    def transform(self, contents, block):
        v = variableAssignments(contents)
        if not v:
            return self.error(u"No filename.")
        else:
            name = pathjoin([config.includePath, v[0][0]])
        try:
            source = open(name)
        except IOError:
            return self.error(u"Can't open \"%s\"." % name)

        if block:
            for line in block:
                v = variableAssignments(line)
                if v:
                    self.vars.update(dict(v))

        return variableSubstitutions(EscapeTransform(source), self.vars)

class Rot13(Extension):
    """
    Hide text by rotating letters 13 places; handy for text that is
    unhidden only on user request (like spoilers in reviews).
    """
    table = dict( zip( map( ord,
    list( u"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz" ) ),
    list( u"NOPQRSTUVWXYZABCDEFGHIJKLMnopqrstuvwxyzabcdefghijklm" ) ) )

    def __init__(self):
        Extension.__init__(self)

    def transform(self, contents, block):
        if contents:
            yield contents.translate(Rot13.table)
        if block:
            for line in block:
                yield line.translate(Rot13.table)

class CaptionedImage(Extension):
    pass

class CaptionedTable(Extension):
    pass

config.parsingContext.addExtension(u"", Default())
config.parsingContext.addExtension(u"comment", Comment())
config.parsingContext.addExtension(u"raw", EscapeText())
if config.includePath:
    config.parsingContext.addExtension(u"include", IncludeFile())
config.parsingContext.addExtension(u"rot13", Rot13())
config.parsingContext.addExtension(u"cimage", CaptionedImage())
config.parsingContext.addExtension(u"ctable", CaptionedTable())

# End of code

if __name__ == "__main__":
    import doctest
    doctest.testmod()

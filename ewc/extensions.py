#!/usr/bin/env python
#
# extensions.py: A module from EWC (http://piclab.com/ewc/).
#
"""
Handling programmable extensions.
"""

class Extension(object):
    def __init__(self):
        pass


class Default(Extension):
    pass


class Comment(Extension):
    pass


class Rot13(Extension):
    pass


class Raw(Extension):
    pass


class Include(Extension):
    pass


builtins = {
    "":         Default(),
    "comment":  Comment(),
    "rot13":    Rot13(),
    "raw":      Raw(),
    "include":  Include(),
}

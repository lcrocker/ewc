#!/usr/bin/env python
#
# namespaces.py: A module from EWC (http://piclab.com/ewc/).
#
"""
Handling hypertext link and image namespaces.
Most users will just want to change the paths in the Local namespace
using the functions in Parser(), but finer control can be achieved here.
"""

class Namespace(object):
    def __init__(self):
        pass


class Local(Namespace):
    def __init__(self):
        self.link_pattern = "/w/{0}.html"
        self.image_pattern = "/i/{0}"

    def get_link_pattern(self): return self.link_pattern
    def set_link_pattern(self, p): self.link_pattern = p
    def get_image_pattern(self): return self.image_pattern
    def set_image_pattern(self, p): self.image_pattern = p


class Wikipedia(Namespace):
    pass


class Google(Namespace):
    pass


class Dictionary(Namespace):
    pass


builtins = {
    "":         Local(),
    "wp":       Wikipedia(),
    "g":        Google(),
    "d":        Dictionary(),
}

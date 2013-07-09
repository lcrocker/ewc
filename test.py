#!/usr/bin/env python
#

import xml.etree.ElementTree as etree
import ewc


def run_tests():
    f = open("README")
    p = ewc.parser.Parser()
    root = p.parse(f)
    print(etree.tostring(root))


if __name__ == "__main__":
    run_tests()

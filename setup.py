#!/usr/bin/env python

from distutils.core import setup

setup(  name = "EWC",
        version = "0.1",
        description = "Extended WikiCreole parsing library and utilities",
        author = "Lee Daniel Crocker",
        author_email = "lee@piclab.com",
        license = "Public Domain",
        url = "http://piclab.com/ewc/",
        download_url = "http://piclab.com/ewc/downloads/ewc-0.1.zip",
        provides = ["ewc"],
        packages = ["ewc"],
        scripts = ["scripts/ewc2html"],
        classifiers = [
            "Development Status :: 2 - Pre-Alpha",
            "Environment :: Console",
            "Intended Audience :: Developers",
            "License :: Public Domain",
            "Natural Language :: English",
            "Operating System :: OS Independent",
            "Programming Language :: Python",
            "Topic :: Software Development :: Libraries :: Python Modules",
            "Topic :: Text Processing :: Markup",
        ],
        long_description = """
The EWC package implements an extended and extensible implementation of the
WikiCreole (http://wikicreole.org/) markup language.
It includes the "ewc" Python module and command-line utilities.
"""
    )

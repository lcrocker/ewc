#!/usr/bin/env python
"""
Code to use EWC as a filter for Django templates.
"""

from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
from django import template
from django.conf import settings

import ewc.config

# Customize ewc.config settings here if desired, for example:
#
# ewc.config.localLinkPattern = "/w/%s.html"
# ewc.config.localImagePattern = "/images/%s"
# ewc.config.includePath = "/includes"

register = template.Library()

# Replace includefile filter to include wiki pages
#

@register.filter
@stringfilter
def creole(ins, arg=None):
    try:
        import ewc.parser
    except ImportError:
        if settings.DEBUG:
            raise template.TemplateSyntaxError, "Error in {% creole %} filter: EWC library not found."
        return u""
    else:
        depth = 0
        if arg:
            try:
                depth = int(arg)
            except:
                pass
        return mark_safe(ewc.parser.convertString(ins, depth))

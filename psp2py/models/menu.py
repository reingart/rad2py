# -*- coding: utf-8 -*-
# this file is released under public domain and you can use without limitations
#########################################################################
## Customize your APP title, subtitle and menus here
#########################################################################

response.title = request.application
response.subtitle = T('customize me!')

#http://dev.w3.org/html5/markup/meta.name.html
response.meta.author = 'Mariano Reingart'
response.meta.description = 'Personal Software Process support webapp'
response.meta.keywords = 'web2py, python, framework, psp'
response.meta.generator = 'Web2py Enterprise Framework'
response.meta.copyright = 'Copyright 2011'


##########################################
## this is the main application menu
## add/remove items as required
##########################################

response.menu = [
    (T('Home'), False, URL('default','index'), []),
    (T('Projects'), False, URL('projects','index'), [
        (T('Search'), False, URL('projects','search'), []),
        (T('Create'), False, URL('projects','create'), []),
    ]),
    (T('PROBE'), False, URL('probe','index'), [
        (T('Categorize'), False, URL('probe','categorize'), []),
        (T('Reuse Library'), False, URL('probe','library'), []),
        (T('Size Log-Normal Distribution'), False, URL('probe','normal_distribution.png'), []),
    ]),
    (T('Estimate'), False, URL('estimate','index'), [
        (T('Correlation'), False, URL('estimate','correlation'), []),
        (T('Significance'), False, URL('estimate','significance'), []),
        (T('Time in phase'), False, URL('estimate','time_in_phase'), []),
        (T('Size vs Time Linear Regression'), False, URL('estimate','linear_regression.png'), []),
    ]),
    ]

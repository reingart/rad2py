#!/usr/bin/env python
# coding:utf-8

"Integration of several python code checkers"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"

import os
import compiler

import pep8
import pyflakes.checker


# PEP8 Coding Standar

class PEP8(pep8.Checker):
    def __init__(self, filename, lines=None):
        self.errors = []
        pep8style = pep8.StyleGuide(parse_argv=False, config_file=False)
        options = pep8style.options
        options.prog = os.path.basename(filename)
        options.exclude = []
        options.filename = filename
        options.select = []
        options.ignore = []
        options.verbose = 0
        #options.ignore = pep8.DEFAULT_IGNORE.split(',')
        options.counters = {'physical lines': 0, 'logical lines': 0,}
        options.messages = {}
        pep8.Checker.__init__(self, filename)
        self.check_all()

    def report_error(self, line_number, offset, text, check):
        filename = self.filename
        error = dict(summary=text, type=30, 
                     filename=filename, lineno=line_number, offset=offset+1)
        self.errors.append(error)
        
    def __iter__(self):
        for error in self.errors:
            yield error


# PyFlakes Sanity Checks

class PyFlakes(object):

    def __init__(self, filename):
        tree = compiler.parse(open(filename).read())
        self.checker = pyflakes.checker.Checker(tree, filename)
        self.checker.messages.sort(lambda a, b: cmp(a.lineno, b.lineno))

    def __iter__(self):
        for msg in self.checker.messages:
            filename = msg.filename
            text = msg.message % msg.message_args
            lineno = msg.lineno
            error = dict(summary=text, type=40, 
                         filename=filename, lineno=lineno, offset=1)
            yield error



def check(filename):
    "Try all available checkers and return all defects founds"
    for defect in PEP8(filename):
        yield defect
    for defect in PyFlakes(filename):
        yield defect
    
        
if __name__ == '__main__':
    for e in check("hola.py"):
        print e

    

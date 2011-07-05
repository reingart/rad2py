#!/usr/bin/env python
# coding:utf-8

"Integration of several python code checkers"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"

import os
import pep8

# PEP8 Coding Standar

class Options(object):
    pass

class PEP8(pep8.Checker):
    def __init__(self, filename, lines=None):
        self.errors = []
        options = pep8.options = Options()
        options.prog = os.path.basename(filename)
        options.exclude = []
        options.filename = filename
        options.select = []
        options.ignore = []
        options.verbose = 0
        #options.ignore = pep8.DEFAULT_IGNORE.split(',')
        options.physical_checks = pep8.find_checks('physical_line')
        options.logical_checks = pep8.find_checks('logical_line')
        options.counters = {} #dict.fromkeys(pep8.BENCHMARK_KEYS, 0)
        options.messages = {}
        pep8.Checker.__init__(self, filename)
        self.check_all()

    def report_error(self, line_number, offset, text, check):
        filename = self.filename
        error = dict(description=text, type=30, filename=filename, lineno=line_number, offset=offset+1)
        self.errors.append(error)
        
    def __iter__(self):
        for error in self.errors:
            yield error

        
if __name__ == '__main__':
    p8 = PEP8("hola.py")
    for e in p8:
        print e
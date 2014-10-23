#!/usr/bin/env python
# coding:utf-8

"Integration of several python testers"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"

import os
import wx

from doctest import DocTestParser, DocTestRunner


# Python Basic DocTest Suite

def doctestfile(filename, module_relative=True, name=None, package=None,
             globs=None, verbose=None, report=True, optionflags=0,
             extraglobs=None, raise_on_error=False, parser=DocTestParser(),
             encoding=None, compileflags=None):

    text =  open(filename).read()

    # If no name was given, then use the file's name.
    if name is None:
        name = os.path.basename(filename)

    # Assemble the globals.
    if globs is None:
        globs = {}
    else:
        globs = globs.copy()
    if extraglobs is not None:
        globs.update(extraglobs)

    defects = []
    class CustomDocTestRunner(DocTestRunner):
        def report_failure(self, out, test, example, got):
            text = "doctest for %s failed, want %s got %s" % (
                example.source.strip(), example.want.split()[0], got)
            lineno = example.lineno
            error = dict(summary=text, type=60, 
                         filename=filename, lineno=lineno+1, offset=1)
            defects.append(error)
            
        def report_unexpected_exception(self, out, test, example, exc_info):
            text = "doctest for %s failed, exception %s" % (
                example.source.strip(), repr(exc_info[1]))
            lineno = example.lineno
            error = dict(summary=text, type=80, 
                         filename=filename, lineno=lineno+1, offset=1)
            defects.append(error)

    runner = CustomDocTestRunner(verbose=verbose, optionflags=optionflags)

    if encoding is not None:
        text = text.decode(encoding)

    # compile and execute the file to get the global definitions
    exec compile(text, filename, "exec") in globs

    # Read the file, convert it to a test, and run it.
    tests = parser.get_doctest(text, globs, name, filename, 0)
    
    count, fail = runner.run(tests)

    if not count:
        wx.MessageBox("No doc tests could be run from: %s module" % filename, "No doc tests found", wx.ICON_ERROR)

    for defect in defects:
        yield defect

def unittestfile(filename):
    # unit test using pytong: http://code.google.com/p/pytong
    import pytong
    pytong.filename = filename
    frame = pytong.Frame("PyTong: %s" % filename)
    if frame.Load():
        # show and start all tests (get root)
        frame.Show()
        item = frame.tree.GetRootItem()
        frame.RunItem(item)
        while frame.running:
            wx.YieldIfNeeded()
        for result in frame.results:
            if not result.wasSuccessful():
                for error in result.errors:
                    defect = dict(summary="ERROR IN " + error[0].__str__(), 
                                  description=error[1],
                                  type=60, filename=filename, lineno=None, offset=1)
                    yield defect
                for error in result.failures:
                    defect = dict(summary="FAILURE IN " + error[0].__str__(), 
                                  description=error[1],
                                  type=60, filename=filename, lineno=None, offset=1)
                    yield defect
    else:
        frame.Destroy()
    
def test(filename):
    "Try all available testers and return all defects founds"
    cdir, filen = os.path.split(os.path.abspath(filename))
    print cdir, filen, os.path.abspath(filename)
    if not cdir: 
        cdir = "."
    cwd = os.getcwd()
    try:
        os.chdir(cdir)

        for defect in doctestfile(filename):
            yield defect
        
        for defect in unittestfile(filename):
            yield defect
    
    finally:
        os.chdir(cwd)


if __name__ == '__main__':
    for e in test("hola.py"):
        print e

    

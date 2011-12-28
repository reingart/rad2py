#!/usr/bin/env python
# coding:utf-8

"Integrated WxPython Shell"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"

# based on picalo implementation
# new __main__ based on web2py.gluon.contrib.shell (google GAE)


import new
import time
import os
import traceback
import sys

import StringIO
import wx.py


class LocalInterpreter(wx.py.interpreter.Interpreter):
    "Customized interpreter for local execution (handling locals and globals)"

    def __init__(self, locals, rawin, stdin, stdout, stderr, 
                 ps1='>>>', ps2='...',
                 globals=None,
                 ):
        """Create an interactive interpreter object."""
        wx.py.interpreter.Interpreter.__init__(self, locals=locals, rawin=rawin, 
                             stdin=stdin, stdout=stdout, stderr=stderr)
        sys.ps1 = ps1
        sys.ps2 = ps2
        self.globals = globals or {}
        
    def runcode(self, code):
        """Execute a code object.

        When an exception occurs, self.showtraceback() is called to
        display a traceback.  All exceptions are caught except
        SystemExit, which is reraised.

        A note about KeyboardInterrupt: this exception may occur
        elsewhere in this code, and may not always be caught.  The
        caller should be prepared to deal with it.

        """
        try:
            exec code in self.globals, self.locals
        except SystemExit:
            raise
        except:
            self.showtraceback()


class Shell(wx.py.shell.Shell):
    "Customized version of PyShell"
    def __init__(self, parent):
        wx.py.shell.Shell.__init__(self, parent, InterpClass=LocalInterpreter)
        self.console = None
     
    def onCut(self, event=None):
        self.Cut()
    def onCopy(self, event=None):
        self.Copy()
    def onPaste(self, event=None):
        self.Paste()
    def onSelectAll(self, event=None):
        self.SelectAll()
    
    def raw_input(self, prompt=""):
        "Return string based on user input (in a separate console if available)"
        if self.console:
            if prompt:
                self.console.write(prompt)
            return self.console.readline()
        else:
            return wx.py.shell.Shell.raw_input(self, prompt)

    def RunScript(self, code, syspath_dirs=None, debugger=None, console=None):
        '''Runs a script in the shell.

           @param code          The actual code object (not the filename).
           @param syspath_dirs  A list of directories to add to sys.path during the run.
        '''
        # save sys.stdout
        oldsfd = sys.stdin, sys.stdout, sys.stderr
        try:
            # save the current sys.path, then add any directories to it
            syspath = sys.path
            if syspath_dirs:
                sys.path = syspath_dirs + sys.path

            # redirect standard streams
            if console:
                sys.stdin = sys.stdout = sys.stderr = console
                self.console = console
            else:
                sys.stdin, sys.stdout, sys.stderr =  self.interp.stdin, self.interp.stdout, self.interp.stderr

            # create a dedicated module to be used as __main__ (globals)
            statement_module = new.module('__main__')
            import __builtin__
            statement_module.__builtins__ = __builtin__
            # sys.modules['__main__'] = statement_module    ## dangerous...

            # update the ui
            self.write(os.linesep)
            # run the script (either the interp and bdb calls exec!)
            if not debugger:
                self.interp.globals = statement_module.__dict__
                self.interp.locals = self.interp.globals
                self.interp.runcode(code)
            else:
                debugger.Run(code, interp=self.interp, 
                                   globals=statement_module.__dict__,
                                   locals=None)
            self.prompt()

        finally:
            # set the system path back to what it was before the script
            sys.path = syspath
            # set the title back to normal
            sys.stdin, sys.stdout, sys.stderr = oldsfd
            self.console = console


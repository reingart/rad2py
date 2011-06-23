#!/usr/bin/env python
# coding:utf-8

"Integrated WxPython Shell"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"

# based on picalo implementation


import time
import os
import traceback
import sys

import StringIO
import wx.py


class Shell(wx.py.shell.Shell):
    "Customized version of PyShell"
    def __init__(self, parent):
        wx.py.shell.Shell.__init__(self, parent)
     
    def onCut(self, event=None):
        self.Cut()
    def onCopy(self, event=None):
        self.Copy()
    def onPaste(self, event=None):
        self.Paste()
    def onSelectAll(self, event=None):
        self.SelectAll()

    def RunScript(self, code, syspath_dirs=None, debugger=None):
        '''Runs a script in the shell.

           @param code          The actual code object (not the filename).
           @param syspath_dirs  A list of directories to add to sys.path during the run.
        '''
        # save sys.stdout
        oldsfd = sys.stdin, sys.stdout, sys.stderr
        try:
            # redirect standard streams
            sys.stdin, sys.stdout, sys.stderr =  self.interp.stdin, self.interp.stdout, self.interp.stderr

            # save the current sys.path, then add any directories to it
            syspath = sys.path
            if syspath_dirs:
                sys.path = syspath_dirs + sys.path

            # update the ui
            self.write(os.linesep)
            # run the script (either the interp and bdb calls exec!)
            if not debugger:
                self.interp.runcode(code)
            else:
                debugger.Run(code, locals=self.interp.locals)
            self.prompt()

        finally:
            # set the system path back to what it was before the script
            sys.path = syspath
            # set the title back to normal
            sys.stdin, sys.stdout, sys.stderr = oldsfd



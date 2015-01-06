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


class Interpreter(wx.py.interpreter.Interpreter):
    "Customized interpreter for local execution (handling locals and globals)"

    def __init__(self, locals, rawin, stdin, stdout, stderr, 
                 ps1='>>> ', ps2='... ',
                 globals=None,
                 debugger=None,
                 ):
        """Create an interactive interpreter object."""
        wx.py.interpreter.Interpreter.__init__(self, locals=locals, rawin=rawin, 
                             stdin=stdin, stdout=stdout, stderr=stderr)
        sys.ps1 = ps1
        sys.ps2 = ps2
        self.globals = globals or {}
        self.debugger = debugger
        
    def runsource(self, source):
        """Compile and run source code in the interpreter."""
        if self.debugger:
            text = self.debugger.Exec(source, 
                                     write=self.stdout.write, 
                                     readline=self.stdin.readline)
            self.stdout.write(text)
            self.stdout.write(os.linesep)
            return False    # no line continuation in debug mode by now
        else:
            return wx.py.interpreter.Interpreter.runsource(self, 
                        source)


    def getAutoCompleteList(self, command='', *args, **kwds):
        root = wx.py.introspect.getRoot(command, terminator=".")
        if self.debugger:
            l = self.debugger.GetAutoCompleteList(root)
        else:
            l = wx.py.interpreter.Interpreter.getAutoCompleteList(self, 
                        command, *args, **kwds)
        return l

    def getCallTip(self, command='', *args, **kwds):
        root = wx.py.introspect.getRoot(command, terminator="(")
        if self.debugger:
            calltip = self.debugger.GetCallTip(root)
        else:
            calltip = wx.py.interpreter.Interpreter.getCallTip(self, 
                        command, *args, **kwds)
        return calltip


class Shell(wx.py.shell.Shell):
    "Customized version of PyShell"
    def __init__(self, parent, debugger):
        wx.py.shell.Shell.__init__(self, parent, InterpClass=Interpreter,
                                   debugger=debugger)
        self.console = None
        self.has_focus = False
        self.Bind(wx.EVT_SET_FOCUS, self.OnFocus)
        self.Bind(wx.EVT_KILL_FOCUS, self.OnFocus)
        
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
    
    def OnFocus(self, evt):
        self.has_focus =  evt.GetId() == wx.EVT_SET_FOCUS
        evt.Skip()

    def HasFocus(self):
        "emulate HasFocus for older wxpython versions"
        return self.has_focus

    def OnKeyDown(self, event):
        "Handle key presses (overrides Shell default method)"
        key = event.GetKeyCode()
        # use arrow up/down for history and tab for autocompletion
        # if autocomplete/calltip is active, proced with normal behavior
        if self.AutoCompActive() and not self.CallTipActive():
            super(Shell, self).OnKeyDown(event)
        elif key == wx.WXK_UP and self.CanEdit():
            self.OnHistoryReplace(step=+1)
        elif key == wx.WXK_DOWN and self.CanEdit():
            self.OnHistoryReplace(step=-1)
        elif key == wx.WXK_TAB and \
             self.GetCurrentPos() != self.promptPosEnd and \
             self.CanEdit():
            # try to autocomplete:
            self.OnCallTipAutoCompleteManually(event.ShiftDown())
            if not self.AutoCompActive() and not self.CallTipActive():
                # show autocomplete form history
                self.OnShowCompHistory()
        else:
            super(Shell, self).OnKeyDown(event)

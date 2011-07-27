#!/usr/bin/env python
# coding:utf-8

"Integrated Debugger"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"

# based on idle, inspired by pythonwin implementation

import bdb
import os
import sys
import wx

# Define notification event for thread completion
EVT_DEBUG_ID = wx.NewId()


class DebugEvent(wx.PyEvent):
    """Simple event to carry arbitrary result data."""
    def __init__(self, filename, lineno):
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_DEBUG_ID)
        self.data = filename, lineno


class Debugger(bdb.Bdb):

    def __init__(self, gui=None):
        bdb.Bdb.__init__(self)
        self.frame = None
        self.interacting = 0
        self.waiting = False
        self.gui = gui # for callbacks

    def user_line(self, frame):
        self.interaction(frame)

    def user_exception(self, frame, info):
        self.interaction(frame, info)

    def Run(self, code, interp=None, *args, **kwargs):
        try:
            self.interp = interp
            self.interacting = 1
            return self.run(code, *args, **kwargs)
        finally:
            self.interacting = 0

    def check_interaction(fn):
        "Decorator for exclusive functions (not allowed during interaction)"
        def check_fn(self, *args, **kwargs):
            if not self.waiting:
                wx.Bell()
            else:
                fn(self, *args, **kwargs)
        return check_fn

    def interaction(self, frame, info=None):
        code, lineno = frame.f_code, frame.f_lineno
        filename = code.co_filename
        basename = os.path.basename(filename)
        message = "%s:%s" % (basename, lineno)
        if code.co_name != "?":
            message = "%s: %s()" % (message, code.co_name)
        #  sync_source_line()
        if frame and filename[:1] + filename[-1:] != "<>" and os.path.exists(filename):
            if self.gui:
                # we may be in other thread (i.e. debugging web2py)
                wx.PostEvent(self.gui, DebugEvent(filename, lineno))

        # wait user events (like wxSemaphore.Wait?, see wx.py.shell.readline)
        self.waiting = True    
        self.frame = frame
         # save and change interpreter namespaces to the current frame
        i_locals = self.interp.locals
        self.interp.locals = frame.f_locals
        try:
            while self.waiting:
                wx.YieldIfNeeded()  # hope this is thread safe...
        finally:
            self.waiting = False
            # dereference interpreter namespaces:
            self.interp.locals = i_locals
        self.frame = None

    @check_interaction
    def Continue(self):
        self.set_continue()
        self.waiting = False

    @check_interaction
    def Step(self):
        self.set_step()
        self.waiting = False

    @check_interaction
    def StepReturn(self):
        self.set_return(self.frame)
        self.waiting = False

    @check_interaction
    def Next(self):
        self.set_next(self.frame)
        self.waiting = False

    @check_interaction
    def Quit(self):
        self.set_quit()
        self.waiting = False

    def SetBreakpoint(self, filename, lineno):
        self.set_break(filename, lineno)

    def ClearBreakpoint(self, filename, lineno):
        self.clear_break(filename, lineno)

    def ClearFileBreakpoints(self, filename):
        self.clear_all_file_breaks(filename)


def set_trace():
    Debugger().set_trace()



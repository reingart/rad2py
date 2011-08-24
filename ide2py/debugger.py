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
        self.start_continue = True # continue on first run

    def user_line(self, frame):
        self.interaction(frame)

    def user_exception(self, frame, info):
        if self.gui:
            self.gui.ExceptHook(*info)
        self.interaction(frame, info)

    def Run(self, code, interp=None, *args, **kwargs):
        try:
            self.interp = interp
            self.interacting = self.start_continue and 1 or 2
            return self.run(code, *args, **kwargs)
        finally:
            self.interacting = 0

    def RunCall(self, function, interp=None, *args, **kwargs):
        try:
            self.interp = interp
            self.interacting = self.start_continue and 1 or 2
            return self.runcall(function, *args, **kwargs)
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
        # first callback (Run)?, just continue...
        if self.interacting == 1:
            self.interacting += 1
            self.set_continue()
            return
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
        # copy globals into interpreter, so them can be inspected (DANGEROUS!)
        self.interp.locals.update(frame.f_globals)
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

    @check_interaction
    def Jump(self, lineno):
        arg = int(lineno)
        try:
            self.frame.f_lineno = arg
        except ValueError, e:
            print '*** Jump failed:', e
            return False

    def SetBreakpoint(self, filename, lineno, temporary=0):
        self.set_break(filename, lineno, temporary)

    def ClearBreakpoint(self, filename, lineno):
        self.clear_break(filename, lineno)

    def ClearFileBreakpoints(self, filename):
        self.clear_all_file_breaks(filename)

    def do_clear(self, arg):
        # required by BDB to remove temp breakpoints!
        err = self.clear_bpbynumber(arg)
        if err:
            print '*** DO_CLEAR failed', err
                        
    def inspect(self, arg):
        try:
            return eval(arg, self.frame.f_globals,
                        self.frame.f_locals)
        except:
            t, v = sys.exc_info()[:2]
            if isinstance(t, str):
                exc_type_name = t
            else: exc_type_name = t.__name__
            return '*** %s: %s' % (exc_type_name, repr(v))

    def reset(self):
        bdb.Bdb.reset(self)
        self.waiting = False
        self.frame = None

    def post_mortem(self, t=None):
        # handling the default
        if t is None:
            # sys.exc_info() returns (type, value, traceback) if an exception is
            # being handled, otherwise it returns None
            t = sys.exc_info()[2]
            if t is None:
                raise ValueError("A valid traceback must be passed if no "
                                 "exception is being handled")

        self.reset()
        
        # get last frame:
        while t is not None:
            frame = t.tb_frame
            t = t.tb_next
            print frame, t
            print frame.f_code, frame.f_lineno

        self.interaction(frame)


def set_trace():
    Debugger().set_trace()



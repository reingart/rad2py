#!/usr/bin/env python
# coding:utf-8

"Integrated Debugger Frontend for qdb"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"

# based on idle, inspired by pythonwin implementation

from threading import Thread, Event
from multiprocessing.connection import Client
import os
import random
import sys
import time
import wx

import qdb

# Define notification event for thread completion
EVT_DEBUG_ID, EVT_READLINE_ID, EVT_WRITE_ID, EVT_EXCEPTION_ID = [wx.NewId() 
    for i in range(4)]


class DebugEvent(wx.PyEvent):
    """Simple event to carry arbitrary result data."""
    def __init__(self, event_type, data=None):
        wx.PyEvent.__init__(self)
        self.SetEventType(event_type)
        self.data = data


class Debugger(qdb.Frontend, Thread):
    "Frontend Visual interface to qdb"

    def __init__(self, gui=None, pipe=None):
        Thread.__init__(self)
        self.frame = None
        self.i = random.randint(1, sys.maxint / 2)  # sequential RPC call id
        self.done = Event()
        self.gui = gui # for callbacks
        self.pipe = None
        self.start_continue = True # continue on first run
        self.rawinput = None
        self.address = ('localhost', 6000)
        self.notifies = []
        self.setDaemon(1)
        self.start()

    def run(self):
        while 1:
            self.pipe = None
            try:
                print "DEBUGGER waiting for connection to", self.address
                self.pipe = Client(self.address, authkey='secret password')
                print "DEBUGGER connected!"
                while 1:
                    qdb.Frontend.run(self)
            except EOFError:
                print "DEBUGGER disconnected..."
                self.pipe.close()
            except IOError, e:
                print "DEBUGGER connection exception:", e
                if self.pipe:
                    self.pipe.close()
                time.sleep(1)

    def call(self, method, *args):
        "Schedule a call for further execution by the thread"
        # this is not a queue, only last call is scheduled:
        self.action = lambda: qdb.Frontend.call(self, method, *args)

    def check_interaction(fn):
        "Decorator for mutually exclusive functions"
        def check_fn(self, *args, **kwargs):
            if self.done.is_set():
                wx.Bell()
            else:
                fn(self, *args, **kwargs)
        return check_fn

    def interaction(self, filename, lineno, line):
        #  sync_source_line()
        if filename[:1] + filename[-1:] != "<>" and os.path.exists(filename):
            if self.gui:
                # we are in other thread so send the event to main thread
                wx.PostEvent(self.gui, DebugEvent(EVT_DEBUG_ID, 
                                                  (filename, lineno)))

        # wait user events: done is a threading.Event (set by the main thread)
        self.done.clear()
        self.done.wait()
        
        # execute user action scheduled by main thread
        self.action()

    def write(self, text):
        wx.PostEvent(self.gui, DebugEvent(EVT_WRITE_ID, text))

    def readline(self):
        self.done.clear()
        wx.PostEvent(self.gui, DebugEvent(EVT_READLINE_ID))
        self.done.wait()
        return self.rawinput

    def exception(self, *args):
        "Notify that a user exception was raised in the backend"
        wx.PostEvent(self.gui, DebugEvent(EVT_EXCEPTION_ID, args))

    # Methods to handle user interaction by main thread bellow:
    
    @check_interaction
    def Readline(self, text):
        self.rawinput = text
        self.done.set()

    @check_interaction
    def Continue(self):
        self.do_continue()
        self.done.set()

    @check_interaction
    def Step(self):
        self.do_step()
        self.done.set()

    @check_interaction
    def StepReturn(self):
        self.do_return()
        self.done.set()

    @check_interaction
    def Next(self):
        self.do_next()
        self.done.set()

    @check_interaction
    def Quit(self):
        self.do_quit()
        self.done.set()

    @check_interaction
    def Jump(self, lineno):
        self.do_jump(lineno)
        self.done.set()

    def SetBreakpoint(self, filename, lineno, temporary=0, cond=None):
        self.do_set_breakpoint(filename, lineno, temporary, cond)
        self.done.set()

    def ClearBreakpoint(self, filename, lineno):
        self.do_clear_breakpoint(filename, lineno)
        self.done.set()

    def ClearFileBreakpoints(self, filename):
        self.do_clear_file_breakpoints(filename)
        self.done.set()

    def Inspect(self, arg):
        try:
            self.do_inspect(arg)
            # we need the result right now:
            return self.action()
        except RPCError, e:
            return u'*** %s' % unicode(e)


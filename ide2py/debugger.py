#!/usr/bin/env python
# coding:utf-8

"Integrated Debugger"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"

# based on idle, inspired by pythonwin implementation

from threading import Thread, Event
from multiprocessing.connection import Client
import os
import random
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


class Debugger(Thread):
    "Frontend Visual interface to qdb"

    def __init__(self, gui=None, pipe=None):
        Thread.__init__(self)
        self.frame = None
        self.i = random.randint(0, sys.maxint / 2)
        self.done = Event()
        self.gui = gui # for callbacks
        self.pipe = None
        self.start_continue = True # continue on first run
        self.address = ('localhost', 6000)
        self.setDaemon(1)
        self.start()

    def run(self):
        while 1:
            print "waiting for connection to", self.address
            self.pipe = Client(self.address, authkey='secret password')
            try:
                while 1:          
                    print "recv..."      
                    request = self.pipe.recv()
                    print "*** DBG <<<< ", request
                    result = None
                    if request.get("error"):
                        print request['error']
                    if request.get('method') == 'interaction':
                        print "%s:%4d\t%s" % request.get("args"),
                        self.interaction(*request.get("args"))
                        result = None
                    if request.get('method') == 'write':
                        print request.get("args")[0],
                    if request.get('method') == 'show_line':
                        print "%s:%4d%s%s\t%s" % request.get("args"),
                    if request.get('method') == 'readline':
                        print "READLINE!!!!"
                        result = 'hola!'#self.gui.console.readline()
                    if result:
                        response = {'version': '1.1', 'id': request.get('id'), 
                                'result': result, 
                                'error': None}
                        self.pipe.send(response)
                        print ">>>", response
            except EOFError:
                print "DEBUGGER disconnected..."
                self.pipe.close()

    def __getattr__(self, attr):
        "Return a pseudomethod that can be called"
        print "PSEUDOMETHOD:", attr
        return lambda *args, **kwargs: self.queue_call(attr, *args)

    def queue_call(self, method, *args):
        "Schedule a call for further execution by the thread"
        print "ACTION SCHEDULED:", method
        self.action = lambda: self.call(method, *args)

    def call(self, method, *args):
        "Actually call the remote method (inside the thread)"
        print "CALLING:", method        
        req = {'method': method, 'args': args, 'id': self.i}
        print "*** DBG >>> ", req
        self.pipe.send(req)
        res = self.pipe.recv()
        print "*** DBG <<< ", res
        if req['id'] != res['id']:
            print "*** wrong packet received!", msg
        self.i += 1

    def check_interaction(fn):
        "Decorator for exclusive functions (not allowed during interaction)"
        def check_fn(self, *args, **kwargs):
            if self.done.is_set():
                print "-+-+-+ Already BuSY!"
                wx.Bell()
            else:
                fn(self, *args, **kwargs)
        return check_fn

    def interaction(self, filename, lineno, line):
        #  sync_source_line()
        if filename[:1] + filename[-1:] != "<>" and os.path.exists(filename):
            if self.gui:
                # we may be in other thread (i.e. debugging web2py)
                print "POSTEVENT", filename, lineno
                wx.PostEvent(self.gui, DebugEvent(filename, lineno))
                wx.Yield()

        # wait user events
        print "WAITING " * 10
        self.done.clear()
        self.done.wait()
        
        # execute user action
        print "ACTION " * 10
        self.action()
        print "DONE " * 10        


    @check_interaction
    def Continue(self):
        self.do_continue()
        self.done.set()

    @check_interaction
    def Step(self):
        print "*** DBG FE *** Step"
        self.do_step()
        self.done.set()

    @check_interaction
    def StepReturn(self):
        self.do_return()
        self.done.set()

    @check_interaction
    def Next(self):
        print "*** DBG FE *** Next"
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

    def SetBreakpoint(self, filename, lineno, temporary=0):
        self.do_set_breakpoint(filename, lineno, temporary)

    def ClearBreakpoint(self, filename, lineno):
        self.do_clear_breakpoint(filename, lineno)

    def ClearFileBreakpoints(self, filename):
        self.do_clear_file_breakpoints(filename)

    def Inspect(self, arg):
        try:
            return self.do_inspect(arg)
        except:
            t, v = sys.exc_info()[:2]
            if isinstance(t, str):
                exc_type_name = t
            else: exc_type_name = t.__name__
            return '*** %s: %s' % (exc_type_name, repr(v))



def set_trace():
    Debugger().set_trace()



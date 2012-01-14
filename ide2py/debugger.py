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
import time
import wx

# Define notification event for thread completion
EVT_DEBUG_ID, EVT_READLINE_ID, EVT_WRITE_ID, EVT_EXCEPTION_ID = [wx.NewId() 
    for i in range(4)]


class DebugEvent(wx.PyEvent):
    """Simple event to carry arbitrary result data."""
    def __init__(self, event_type, data=None):
        wx.PyEvent.__init__(self)
        self.SetEventType(event_type)
        self.data = data


class RPCError(RuntimeError):
    pass


class UserException(RuntimeError):
    pass


class Debugger(Thread):
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
                print "waiting for connection to", self.address
                self.pipe = Client(self.address, authkey='secret password')
                while 1:          
                    print "recv..."
                    if not self.notifies:
                        # wait for a message...
                        request = self.pipe.recv()
                    else:
                        # process an asyncronus notification received earlier 
                        request = self.notifies.pop(0)
                    print "*** DBG <<<< ", request
                    result = None
                    if request.get("error"):
                        print request['error']
                    elif request.get('method') == 'interaction':
                        print "%s:%4d\t%s" % request.get("args"),
                        self.interaction(*request.get("args"))
                        result = None
                    elif request.get('method') == 'write':
                        text = request.get("args")[0]
                        print "WRITE"*10, text
                        wx.PostEvent(self.gui, DebugEvent(EVT_WRITE_ID, text))
                    elif request.get('method') == 'show_line':
                        print "%s:%4d%s%s\t%s" % request.get("args"),
                    elif request.get('method') == 'exception':
                        wx.PostEvent(self.gui, DebugEvent(EVT_EXCEPTION_ID, 
                                                          request.get("args")))
                    elif request.get('method') == 'readline':
                        print "WAITING READLINE!!!!"
                        self.done.clear()
                        wx.PostEvent(self.gui, DebugEvent(EVT_READLINE_ID))
                        self.done.wait()
                        result = self.rawinput
                        print "READLINE: ", result
                    # do not reply notifications (no result)
                    if result:
                        response = {'version': '1.1', 'id': request.get('id'), 
                                'result': result, 
                                'error': None}
                        self.pipe.send(response)
                        print ">>>", response
            except EOFError:
                print "DEBUGGER disconnected..."
                self.pipe.close()
            except IOError:
                print "DEBUGGER cannot connect..."
                if self.pipe:
                    self.pipe.close()
                time.sleep(1)

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
        self.i += 1  # increment the id
        while 1:
            # wait until command acknowledge (response match the request)
            res = self.pipe.recv()
            print "*** DBG <<< ", res
            if 'id' not in res or not res['id']:
                print "*** notification received!", res
                self.notifies.append(res)
            elif 'result' not in res:
                ##print "*** wrong packet received: expecting result", res
                # protocol state is unknown
                self.notifies.append(res)
            elif long(req['id']) != long(res['id']):
                print "*** wrong packet received: expecting id", req['id'], res['id']
                # protocol state is unknown
            elif 'error' in res and res['error']:
                raise RPCError(res['error']['message'])
            else:
                return res['result']

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
                wx.PostEvent(self.gui, DebugEvent(EVT_DEBUG_ID, 
                                                  (filename, lineno)))

        # wait user events
        print "WAITING " * 10
        self.done.clear()
        self.done.wait()
        
        # execute user action
        print "ACTION " * 10
        self.action()
        print "DONE " * 10        

    @check_interaction
    def Readline(self, text):
        print "READLINE TEXT READ: ", text
        self.rawinput = text
        self.done.set()

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
        print "*** DBG FE *** Set Breakpoint"
        self.do_set_breakpoint(filename, lineno, temporary)
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



def set_trace():
    Debugger().set_trace()



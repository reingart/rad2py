#!/usr/bin/env python
# coding:utf-8

"Integrated Debugger Frontend for qdb"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"

# based on idle, inspired by pythonwin implementation

from threading import Thread, Event
from Queue import Queue
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


class LoggingPipeWrapper(object):
    
    def __init__(self, pipe):
        self.__pipe = pipe
    
    def send(self, data):
        print("PIPE:send: %s" % repr(data))
        self.__pipe.send(data)

    def recv(self, *args, **kwargs):
        data = self.__pipe.recv(*args, **kwargs)
        print("PIPE:recv: %s" % repr(data))
        return data
    
    def close(self):
        self.__pipe.close()

        
class Debugger(qdb.Frontend, Thread):
    "Frontend Visual interface to qdb"

    def __init__(self, gui=None, pipe=None):
        Thread.__init__(self)
        qdb.Frontend.__init__(self, pipe)
        self.interacting = Event()  # flag to 
        self.done = Event()         # flag to block for user interaction
        self.attached = Event()     # flag to block waiting for remote side
        self.gui = gui              # wx window for callbacks
        self.start_continue = True  # continue on first run
        self.rawinput = None
        self.breakpoints = {}       # {filename: {lineno: (temp, cond)}
        self.setDaemon(1)           # do not join (kill on termination)
        self.actions = Queue()
        self.start()                # creathe the new thread

    def run(self):
        while 1:
            self.pipe = None
            try:
                self.attached.wait()
                print "DEBUGGER waiting for connection to", self.address
                self.pipe = LoggingPipeWrapper(Client(self.address, authkey=self.authkey))
                print "DEBUGGER connected!"
                while self.attached.is_set():
                    qdb.Frontend.run(self)
            except EOFError:
                print "DEBUGGER disconnected..."
            except IOError, e:
                print "DEBUGGER connection exception:", e
            finally:
                self.detach()
                if self.pipe:
                    self.pipe.close()

    def attach(self, host='localhost', port=6000, authkey='secret password'):
        self.address = (host, port)
        self.authkey = authkey
        self.attached.set()
    
    def detach(self):
        self.attached.clear()

    def is_remote(self):
        return (self.attached.is_set() and 
                self.address[0] not in ("localhost"))

    def call(self, method, *args):
        "Schedule a call for further execution by the thread"
        self.actions.put(lambda: qdb.Frontend.call(self, method, *args))

    def push_actions(self):
        "Execute scheduled actions"
        ret = None
        while not self.actions.empty():
            action = self.actions.get()
            ret = action()
            self.actions.task_done()
        return ret

    def check_interaction(fn):
        "Decorator for mutually exclusive functions"
        def check_fn(self, *args, **kwargs):
            if self.done.is_set():
                wx.Bell()
            else:
                fn(self, *args, **kwargs)
        return check_fn

    def interaction(self, filename, lineno, line):
        self.done.clear()
        self.interacting.set()
        try:
            if self.start_continue is not None:
                print "loading breakpoints...."
                self.LoadBreakpoints()
                if self.start_continue:
                    print "continuing..."
                    self.Continue()
                    self.push_actions()
                    self.start_continue = None
                    return
                self.start_continue = None
                
            #  sync_source_line()
            if filename[:1] + filename[-1:] != "<>" and os.path.exists(filename):
                if self.gui:
                    # we are in other thread so send the event to main thread
                    wx.PostEvent(self.gui, DebugEvent(EVT_DEBUG_ID, 
                                                      (filename, lineno)))

            # wait user events: done is a threading.Event (set by the main thread)
            self.done.wait()
            
            # execute user action scheduled by main thread
            self.push_actions()

            # clean current line
            wx.PostEvent(self.gui, DebugEvent(EVT_DEBUG_ID, (None, None)))
        finally:
            self.interacting.clear()

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

    def Interrupt(self):
        self.interrupt()

    def LoadBreakpoints(self):
        for filename, bps in self.breakpoints.items():
            for lineno, (temporary, cond) in bps.items():
                print "loading breakpoint", filename, lineno
                self.do_set_breakpoint(filename, lineno, temporary, cond)
                self.push_actions()
                # TODO: discard interaction message
                self.pipe.recv()


    def async_push(self, action):
        # if no interaction yet, send an interrupt (step on the next stmt)
        if not self.interacting.is_set():
            self.interrupt()
            cont = True
        else:
            cont = False
        # wait for interaction and send the method request (signal we are done)
        self.interacting.wait()
        action()
        ret = self.push_actions()
        self.interacting.clear()
        self.done.set()
        # if interrupted, send a continue to resume
        if cont:
            self.interacting.wait()
            self.do_continue()
            self.done.set()
        return ret

    def SetBreakpoint(self, filename, lineno, temporary=0, cond=None):
        # store breakpoint
        self.breakpoints.setdefault(filename, {})[lineno] = (temporary, cond)
        # only send if debugger is connected and attached
        if self.pipe and self.attached.is_set():
            action = lambda: self.do_set_breakpoint(filename, lineno, temporary, cond)
            self.async_push(action)
            return True
        else:
            return False

    def ClearBreakpoint(self, filename, lineno):
        try:
            del self.breakpoints[filename][lineno]
            # only send if debugger is connected and attached
            if self.pipe and self.attached.is_set():
                action = lambda: self.do_clear_breakpoint(filename, lineno)
                self.async_push(action)
                return True
            else:
                return False
        except KeyError, e:
            print e

    def ClearFileBreakpoints(self, filename):
        try:
            del self.breakpoints[filename]
            action = self.do_clear_file_breakpoints(filename)
            self.async_push(action)
            return True
        except KeyError, e:
            print e

    def Inspect(self, arg):
        if self.pipe and self.attached.is_set():
            try:
                # we need the result right now:
                return self.async_push(lambda: self.do_inspect(arg))
            except qdb.RPCError, e:
                return u'*** %s' % unicode(e)


    def ReadFile(self, filename):
        "Load remote file"
        from cStringIO import StringIO
        action = lambda: self.do_read(filename)
        data = self.async_push(action)
        return StringIO(data)


if __name__ == '__main__':
    import sys
    
    url = "http://admin:a@localhost:8000/admin/webservices/call/jsonrpc"
    r = simplejsonrpc.ServiceProxy(url, verbose=True)
    
    r.start_debugger('localhost', 6000, 'secret password')
    



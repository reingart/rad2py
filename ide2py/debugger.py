#!/usr/bin/env python
# coding:utf-8

"Integrated Debugger Frontend for qdb"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"

# based on idle, inspired by pythonwin implementation

from threading import Thread, Event, Lock
from Queue import Queue
from multiprocessing.connection import Client
import os
import random
import sys
import time
import wx
import wx.gizmos
from wx.lib.mixins.listctrl import ListCtrlAutoWidthMixin

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
        print("PIPE:send: %s %s %s %s" % (data.get("id"), data.get("method"), data.get("args"), repr(data.get("result",""))[:40]))
        self.__pipe.send(data)

    def recv(self, *args, **kwargs):
        data = self.__pipe.recv(*args, **kwargs)
        print("PIPE:recv: %s %s %s %s" % (data.get("id"), data.get("method"), data.get("args"), repr(data.get("result",""))[:40]))
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
        self.mutex = Lock()         # critical section protection (comm chanel)
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
            if not self.interacting.is_set() or self.done.is_set():
                wx.Bell()
            else:
                if self.mutex.acquire(False):                
                    try:
                        fn(self, *args, **kwargs)
                    finally:
                        self.mutex.release()
        return check_fn
    
    def startup(self):
        # notification sent by _runscript before Bdb.run
        print "loading breakpoints...."
        self.LoadBreakpoints()
        print "enabling call_stack and environment at interaction"
        self.set_params(dict(call_stack=True, environment=True))
        # return control to the backend:
        qdb.Frontend.startup(self)

    def interaction(self, filename, lineno, line, **context):
        self.done.clear()
        self.interacting.set()
        try:
            if self.start_continue:
                print "continuing..."
                self.Continue()
                self.push_actions()
                self.start_continue = None
                return
                
            #  sync_source_line()
            if filename[:1] + filename[-1:] != "<>" and os.path.exists(filename):
                if self.gui:
                    # we are in other thread so send the event to main thread
                    wx.PostEvent(self.gui, DebugEvent(EVT_DEBUG_ID, 
                                                      (filename, lineno, context)))

            # wait user events: done is a threading.Event (set by the main thread)
            self.done.wait()
            
            # execute user action scheduled by main thread
            self.push_actions()

            # clean current line
            wx.PostEvent(self.gui, DebugEvent(EVT_DEBUG_ID, (None, None, None)))
        finally:
            self.interacting.clear()

    def write(self, text):
        wx.PostEvent(self.gui, DebugEvent(EVT_WRITE_ID, text))

    def readline(self):
        # "raw_input" should be atomic and uninterrupted
        self.mutex.acquire()
        try:
            self.done.clear()
            wx.PostEvent(self.gui, DebugEvent(EVT_READLINE_ID))
            self.done.wait()
            return self.rawinput
        finally:
            self.mutex.release()

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
        if not self.mutex.acquire(False):
            return
        try:
            # store breakpoint
            self.breakpoints.setdefault(filename, {})[lineno] = (temporary, cond)
            # only send if debugger is connected and attached
            if self.pipe and self.attached.is_set():
                action = lambda: self.do_set_breakpoint(filename, lineno, temporary, cond)
                self.async_push(action)
                return True
            else:
                return False
        finally:
            self.mutex.release()

    def ClearBreakpoint(self, filename, lineno):
        if not self.mutex.acquire(False):
            return
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
        finally:
            self.mutex.release()
            
    def ClearFileBreakpoints(self, filename):
        if not self.mutex.acquire(False):
            return
        try:
            del self.breakpoints[filename]
            action = self.do_clear_file_breakpoints(filename)
            self.async_push(action)
            return True
        except KeyError, e:
            print e
        finally:
            self.mutex.release()

    def Inspect(self, arg):
        if self.pipe and self.attached.is_set():
            if not self.mutex.acquire(False):
                return
            try:
                # we need the result right now:
                return self.async_push(lambda: self.do_inspect(arg))
            except qdb.RPCError, e:
                return u'*** %s' % unicode(e)
            finally:
                self.mutex.release()

    def ReadFile(self, filename):
        "Load remote file"
        from cStringIO import StringIO
        action = lambda: self.do_read(filename)
        data = self.async_push(action)
        return StringIO(data)

    def GetContext(self):
        self.set_burst(3)
        self.do_where()
        w = self.push_actions()
        ret = []
        for filename, lineno, bp, current, source in w:
            ret.append((filename, lineno, "%s%s" % (bp, current), source))
        d = {'call_stack': ret}
        self.do_environment()
        env = self.push_actions()
        ret = ""
        d['environment'] = env
        return d

    # methods used by the shell:
    
    def Run(self, statement, write=None, readline=None):
        "Run source code statement in debugger context (returns string)"
        if self.pipe and self.attached.is_set():
            if self.mutex.acquire(False):
                old_write = self.write
                old_readline = self.readline
                try:
                    # replace console function
                    if write:
                        self.write = write
                    if readline:
                        self.readline = readline
                    # execute the statement in the remote debugger:
                    ret = self.async_push(lambda: self.do_exec(statement))
                    if isinstance(ret, basestring):
                        return ret
                    else:
                        return str(ret)
                except qdb.RPCError, e:
                    return u'*** %s' % unicode(e)
                finally:
                    self.write = old_write
                    self.readline = readline
                    self.mutex.release()
        return None

    def GetAutoCompleteList(self, expr=''):
        "Return list of auto-completion options for an expression"
        if self.pipe and self.attached.is_set():
            if self.mutex.acquire(False):
                try:
                    cmd = lambda: self.get_autocomplete_list(expr)
                    return self.async_push(cmd)
                except qdb.RPCError, e:
                    return u'*** %s' % unicode(e)
                finally:
                    self.mutex.release()

    def GetCallTip(self, expr):
        "Returns (name, argspec, tip) for an expression"
        if self.pipe and self.attached.is_set():
            if self.mutex.acquire(False):
                try:
                    cmd = lambda: self.get_call_tip(expr)
                    return self.async_push(cmd)
                except qdb.RPCError, e:
                    return u'*** %s' % unicode(e)
                finally:
                    self.mutex.release()


class EnvironmentPanel(wx.Panel):
    def __init__(self, parent=None):
        wx.Panel.__init__(self, parent, -1)
        self.Bind(wx.EVT_SIZE, self.OnSize)

        self.tree = wx.gizmos.TreeListCtrl(self, -1, style =
                                        wx.TR_DEFAULT_STYLE
                                        #| wx.TR_HAS_BUTTONS
                                        #| wx.TR_TWIST_BUTTONS
                                        #| wx.TR_ROW_LINES
                                        #| wx.TR_COLUMN_LINES
                                        #| wx.TR_NO_LINES 
                                        | wx.TR_HIDE_ROOT
                                        | wx.TR_FULL_ROW_HIGHLIGHT
                                   )

        # create some columns
        self.tree.AddColumn("Name")
        self.tree.AddColumn("Type")
        self.tree.AddColumn("Repr")
        self.tree.SetMainColumn(0) # the one with the tree in it...
        self.tree.SetColumnWidth(0, 175)

    def BuildItem(self, item, txt, cols=None):
        child = self.tree.AppendItem(item, txt)
        if cols:
            for i, col in enumerate(cols):
                self.tree.SetItemText(child, col, i+1)
        return child
        
    def BuildTree(self, scopes, sort_order):
        self.tree.DeleteAllItems()
        self.root = self.tree.AddRoot("The Root Item")
        # process locals and globals
        for i, key in enumerate(sort_order):
            vars = scopes.get(key)
            child = self.BuildItem(self.root, key)
            if not vars:
                continue
            for var_name, (var_repr, var_type) in vars.items():
                self.BuildItem(child, var_name, (var_type, var_repr))
            if i == 0:
                self.tree.Expand(child)
        self.tree.Expand(self.root)

    def OnSize(self, evt):
        self.tree.SetSize(self.GetSize())


class StackListCtrl(wx.ListCtrl, ListCtrlAutoWidthMixin):
    "Call stack window (filename lineno flags, source)"
    def __init__(self, parent, filename=""):
        wx.ListCtrl.__init__(self, parent, -1, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        ListCtrlAutoWidthMixin.__init__(self)
        self.parent = parent
        self.InsertColumn(0, "Filename", wx.LIST_FORMAT_LEFT) 
        self.SetColumnWidth(0, 200)
        self.InsertColumn(1, "LineNo", wx.LIST_FORMAT_RIGHT) 
        self.SetColumnWidth(1, 50)
        self.InsertColumn(2, "Flags", wx.LIST_FORMAT_CENTER) 
        self.SetColumnWidth(2, 0)
        self.InsertColumn(3, "Current", wx.LIST_FORMAT_CENTER) 
        self.SetColumnWidth(3, 0)
        self.InsertColumn(4, "source", wx.LIST_AUTOSIZE) 
        self.SetColumnWidth(4, -1)
        self.setResizeColumn(5)

    def AddItem(self, item, key=None):
        index = self.InsertStringItem(sys.maxint, item[0])
        for i, val in enumerate(item[1:]):
            self.SetStringItem(index, i+1, str(val))
    
    def BuildList(self, items):
        self.DeleteAllItems()
        for item in items:
            self.AddItem(item)


class TestFrame(wx.Frame):

    def __init__(self, filename=None):
        wx.Frame.__init__(self, None)
        self.Show()
        self.panel = EnvironmentPanel(self)
        self.panel.BuildTree({'locals': {'saraza': ('str', 'none')}})
        self.SendSizeEvent() 

if __name__ == '__main__':
    
    app = wx.App()
    frame = TestFrame()
    app.MainLoop()
    
    import sys
    
    url = "http://admin:a@localhost:8000/admin/webservices/call/jsonrpc"
    r = simplejsonrpc.ServiceProxy(url, verbose=True)
    
    r.start_debugger('localhost', 6000, 'secret password')
    



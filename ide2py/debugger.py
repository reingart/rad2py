#!/usr/bin/env python
# coding:utf-8

"Integrated Debugger Frontend for qdb"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"

# initally based on idle, inspired by pythonwin implementation

from multiprocessing.connection import Client
import compiler
import os
import sys
import wx
import wx.gizmos
from wx.lib.mixins.listctrl import ListCtrlAutoWidthMixin

import qdb

# Define notification event for thread completion
EVT_DEBUG_ID, EVT_EXCEPTION_ID = [wx.NewId() for i in range(2)]


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
    
    def poll(self):
        return self.__pipe.poll()

        
class Debugger(qdb.Frontend):
    "Frontend Visual interface to qdb"

    def __init__(self, gui=None, pipe=None):
        qdb.Frontend.__init__(self, pipe)
        self.interacting = False    # flag to signal user interaction
        self.attached = False       # flag to signal remote side availability
        self.gui = gui              # wx window for callbacks
        self.post_event = True      # send event to the GUI
        self.start_continue = True  # continue on first run
        self.rawinput = None
        self.filename = self.lineno = None
        self.unrecoverable_error = False
        self.pipe = None
        wx.GetApp().Bind(wx.EVT_IDLE, self.OnIdle) # schedule debugger execution


    def OnIdle(self, event):
        "Debugger main loop: read and execute remote methods"
        try:
            if self.attached:
                while self.pipe.poll():
                    self.run()
        except EOFError:
            print "DEBUGGER disconnected..."
            self.detach()
        except IOError, e:
            print "DEBUGGER connection exception:", e
            self.detach()
        except Exception, e:
            # print the exception message and close (avoid recursion)
            print "DEBUGGER exception", e
            import traceback
            traceback.print_exc()
            import sys;
            sys.exit()

    def init(self, cont=False):
        self.start_continue = cont
        self.unrecoverable_error = None
        
    def attach(self, host='localhost', port=6000, authkey='secret password'):
        self.address = (host, port)
        self.authkey = authkey
        print "DEBUGGER waiting for connection to", self.address
        self.pipe = LoggingPipeWrapper(Client(self.address, authkey=self.authkey))
        print "DEBUGGER connected!"
        self.attached = True
    
    def detach(self):
        self.attached = False
        if self.pipe:
            self.pipe.close()

    def is_remote(self):
        return (self.attached and 
                self.address[0] not in ("localhost"))

    def check_interaction(fn):
        "Decorator for mutually exclusive functions"
        def check_fn(self, *args, **kwargs):
            if not self.interacting or not self.pipe or not self.attached:
                wx.Bell()
                self.gui.ShowInfoBar("not interacting! reach a breakpoint "
                                     "or interrupt the running code (CTRL+I)", 
                                     flags=wx.ICON_INFORMATION, key="debugger")
            else:
                # do not execute if edited (code editions must be checked)
                if self.check_running_code(fn.func_name):
                    self.interacting = False
                    # interaction is done, clean current line marker
                    wx.PostEvent(self.gui, DebugEvent(EVT_DEBUG_ID, (None, None, None, None)))
                    return fn(self, *args, **kwargs)
        return check_fn
    
    def is_waiting(self):
        # check if interaction is banned (i.e. readline!)
        if self.interacting is None:
            self.gui.ShowInfoBar("cannot interrupt now (readline): "
                "debugger is waiting your user input at the Console window",
                flags=wx.ICON_INFORMATION, key="debugger")
            wx.Bell()
            return True

    def force_interaction(fn):
        "Decorator for functions that need to break immediately"
        def check_fn(self, *args, **kwargs):
            # only send if debugger is connected and attached
            if not self.pipe or not self.attached or self.is_waiting():
                return False
            # do not send GUI notifications (to not alter the focus)
            self.post_event = False
            # if no interaction yet, send an interrupt (step on the next stmt)
            if not self.interacting:
                self.interrupt()
                cont = True
            else:
                cont = False
            # wait for interaction:
            while not self.interacting:
                # allow wx process some events 
                wx.SafeYield()      # safe = user input "disabled"
                self.OnIdle(None)   # force pipe processing
            # send the method request                
            ret = fn(self, *args, **kwargs)
            # if interrupted, send a continue to resume
            if cont:
                self.post_event = True
                self.interacting = False
                self.do_continue()
            return True
        return check_fn

    def startup(self):
        "Initialization procedures (called by the backend)"
        # notification sent by _runscript before Bdb.run
        print "loading breakpoints...."
        self.LoadBreakpoints()
        print "enabling call_stack and environment at interaction"
        self.set_params(dict(call_stack=True, environment=True, postmortem=True))
        # return control to the backend:
        qdb.Frontend.startup(self)

    def interaction(self, filename, lineno, line, **context):
        "Start user interaction -show current line- (called by the backend)"
        self.interacting = True
        try:
            if self.start_continue:
                self.Continue()
                self.start_continue = None
                return
                
            #  sync_source_line()
            self.filename = self.orig_line = self.lineno = None
            if filename[:1] + filename[-1:] != "<>" and os.path.exists(filename):
                self.filename = filename
                self.orig_line = line.strip().strip("\r").strip("\n")
                self.lineno = lineno
                if self.gui and self.post_event:
                    # send the event to mark the current line
                    wx.PostEvent(self.gui, DebugEvent(EVT_DEBUG_ID, 
                                                      (filename, lineno, context, line)))
                else:
                    # ignore this (async command) and reenable notifications
                    self.post_event = True
        finally:
            pass
            
    def write(self, text):
        "ouputs a message (called by the backend)"
        self.gui.Write(text)

    def readline(self):
        "returns a user input (called by the backend)"
        # "raw_input" should be atomic and uninterrupted
        try:
            self.interacting = None
            return self.gui.Readline()
        finally:
            self.interacting = False

    def exception(self, *args):
        "Notify that a user exception was raised in the backend"
        if not self.unrecoverable_error:
            wx.PostEvent(self.gui, DebugEvent(EVT_EXCEPTION_ID, args))
            self.unrecoverable_error = u"%s" % args[0]

    def check_running_code(self, func_name):
        "Edit and continue functionality -> True=ok or False=restart"
        # only check edited code for the following methods:
        if func_name not in ("Continue", "Step", "StepReturn", "Next"):
            return True
        if self.filename:
            curr_line = self.gui.GetLineText(self.filename, self.lineno)
            curr_line = curr_line.strip().strip("\r").strip("\n")
        # check if no exception raised
        if self.unrecoverable_error:
            dlg = wx.MessageDialog(self.gui, 
                   "Unrecoverable error: %s\n\n"
                   "Do you want to QUIT the program?"
                   % unicode(self.unrecoverable_error), 
                   "Unable to interact (Post-Mortem)",
                   wx.YES_NO | wx.ICON_EXCLAMATION)
            quit = dlg.ShowModal() == wx.ID_YES              
            dlg.Destroy()
            if quit:
                self.do_quit()
            return False
        # check current text source code against running code
        if self.lineno is not None and self.orig_line != curr_line:
            print "edit_and_continue..."
            try:
                compiler.parse(curr_line)
                self.set_burst(3)
                self.do_exec(curr_line)
                print "executed", curr_line
                ret = self.do_jump(self.lineno+1)
                print "jump", ret
                if ret:
                    raise RuntimeError("Cannot jump to ignore modified line!")
            except Exception, e:
                dlg = wx.MessageDialog(self.gui, "Exception: %s\n\n"
                       "Your changes requires restart (or undo to continue)." 
                       % unicode(e), 
                       "Unable to modify running code",
                       wx.OK | wx.ICON_EXCLAMATION)
                dlg.ShowModal()
                dlg.Destroy()
                return False
        return True

    # Methods to handle user interaction by main thread bellow:
    
    @check_interaction
    def Continue(self, filename=None, lineno=None):
        "Execute until the program ends, a breakpoint is hit or interrupted"
        if filename and lineno:
            # set a temp breakpoint (continue to...)
            self.set_burst(2)
            self.do_set_breakpoint(filename, lineno, temporary=1)
        self.do_continue()

    @check_interaction
    def Step(self):
        "Execute until the next instruction (entering to functions)"
        self.do_step()

    @check_interaction
    def StepReturn(self):
        "Execute until the end of the current function"
        self.do_return()

    @check_interaction
    def Next(self):
        "Execute until the next line (not entering to functions)"
        self.do_next()

    @force_interaction
    def Quit(self):
        "Terminate the program being debugged"
        self.do_quit()

    @check_interaction
    def Jump(self, lineno):
        "Set next line to be executed"
        ret = self.do_jump(lineno)
        if ret:
            self.gui.ShowInfoBar("cannot jump: %s" % ret,
                         flags=wx.ICON_INFORMATION, key="debugger")

    def Interrupt(self):
        "Stop immediatelly (similar to Ctrl+C but program con be resumed)"
        if self.attached and not self.is_waiting():
            self.interrupt()

    def LoadBreakpoints(self):
        "Set all breakpoints (remotelly, used at initialization)"
        # get a list of {filename: {lineno: (temp, cond)}
        for filename, bps in self.gui.GetBreakpoints():
            for lineno, (temporary, cond) in bps.items():
                print "loading breakpoint", filename, lineno
                self.do_set_breakpoint(filename, lineno, temporary, cond)

    @force_interaction
    def SetBreakpoint(self, filename, lineno, temporary=0, cond=None):
        "Set the specified breakpoint (remotelly)"
        self.do_set_breakpoint(filename, lineno, temporary, cond)

    @force_interaction
    def ClearBreakpoint(self, filename, lineno):
        "Remove the specified breakpoint (remotelly)"
        self.do_clear_breakpoint(filename, lineno)
            
    @force_interaction
    def ClearFileBreakpoints(self, filename):
        "Remove all breakpoints set for a file (remotelly)"
        self.do_clear_file_breakpoints(filename)

    # modal functions required by Eval (must not block):
    
    def modal_write(self, text):
        "Aux dialog to show output (modal for Exec/Eval)"
        dlg = wx.MessageDialog(self.gui, text, "Debugger console output", 
               wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def modal_readline(self, msg='Input required', default=''):
        "Aux dialog to request user input (modal for Exec/Eval)"
        dlg = wx.TextEntryDialog(self.gui, msg,
                'Debugger console input', default)
        if dlg.ShowModal() == wx.ID_OK:
            return dlg.GetValue() 
        dlg.Destroy()
        
    @check_interaction
    def Eval(self, arg):
        "Returns the evaluation of an expression in the debugger context"
        if self.pipe and self.attached:
            try:
                old_write = self.write
                old_readline = self.readline
                # replace console functions
                self.write = self.modal_write
                self.readline = self.modal_readline
                # we need the result right now:
                return self.do_eval(arg)
            except qdb.RPCError, e:
                return u'*** %s' % unicode(e)
            finally:
                self.write = old_write
                self.readline = old_readline

    @check_interaction
    def ReadFile(self, filename):
        "Load remote file"
        from cStringIO import StringIO
        data = self.do_read(filename)
        return StringIO(data)

    @check_interaction
    def GetContext(self):
        "Request call stack and environment (locals/globals)"
        self.set_burst(3)
        w = self.do_where()
        ret = []
        for filename, lineno, bp, current, source in w:
            ret.append((filename, lineno, "%s%s" % (bp, current), source))
        d = {'call_stack': ret}
        env = self.do_environment()
        ret = ""
        d['environment'] = env
        return d

    # methods used by the shell:
    
    def Exec(self, statement, write=None, readline=None):
        "Exec source code statement in debugger context (returns string)"
        if statement == "" or not self.attached:
            # 1. shell seems to call Exec without statement on init
            # 2. if not debuging, exec on the current local wx shell
            pass  
        elif not self.interacting:
            wx.Bell()
            return u'*** no debugger interaction (stop first!)'
        else:
            old_write = self.write
            old_readline = self.readline
            try:
                # replace console function
                if write:
                    self.write = write
                if readline:
                    self.readline = readline
                # execute the statement in the remote debugger:
                ret = self.do_exec(statement)
                if isinstance(ret, basestring):
                    return ret
                else:
                    return str(ret)
            except qdb.RPCError, e:
                return u'*** %s' % unicode(e)
            finally:
                self.write = old_write
                self.readline = old_readline
        return None

    def GetAutoCompleteList(self, expr=''):
        "Return list of auto-completion options for an expression"
        if self.pipe and self.attached and self.interacting:
            try:
                return self.get_autocomplete_list(expr)
            except qdb.RPCError, e:
                return u'*** %s' % unicode(e)

    def GetCallTip(self, expr):
        "Returns (name, argspec, tip) for an expression"
        if self.pipe and self.attached and self.interacting:
            try:
                return self.get_call_tip(expr)
            except qdb.RPCError, e:
                return u'*** %s' % unicode(e)
    

class EnvironmentPanel(wx.Panel):
    def __init__(self, parent=None):
        wx.Panel.__init__(self, parent, -1)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.debugger = parent.debugger
        self.tree = wx.gizmos.TreeListCtrl(self, -1, style =
                                        wx.TR_DEFAULT_STYLE
                                        | wx.TR_HIDE_ROOT
                                        | wx.TR_FULL_ROW_HIGHLIGHT
                                   )

        # create some columns
        self.tree.AddColumn("Name")
        self.tree.AddColumn("Type")
        self.tree.AddColumn("Repr")
        self.tree.SetMainColumn(0) # the one with the tree in it...
        self.tree.SetColumnWidth(0, 175)
        self.tree.Bind(wx.EVT_TREE_ITEM_ACTIVATED, self.OnActivate)

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

    def OnActivate(self, evt):
        "When a item is clicked, ask for a new value and try to update it"
        # get name of activated item:
        var = self.tree.GetItemText(evt.GetItem())
        if var:
            # get current value (default) and open a dialog asking the new one
            val = self.tree.GetItemText(evt.GetItem(), 2)
            val = self.debugger.modal_readline("New value for %s" % var, val)
            # only edit if user has input text
            if val:
                ret = self.debugger.Exec("%s = %s" % (var, val))
                # return value should be None, if not, show error message:
                if ret != 'None':
                    self.debugger.modal_write(ret)


class StackListCtrl(wx.ListCtrl, ListCtrlAutoWidthMixin):
    "Call stack window (filename lineno flags, source)"
    def __init__(self, parent, filename=""):
        wx.ListCtrl.__init__(self, parent, -1, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        ListCtrlAutoWidthMixin.__init__(self)
        self.parent = parent
        self.InsertColumn(0, "Filename", wx.LIST_FORMAT_RIGHT) 
        self.SetColumnWidth(0, 100)
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
    



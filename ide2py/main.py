#!/usr/bin/env python
# coding:utf-8

"Pythonic Integrated Development Environment for Rapid Application Development"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"
__version__ = "0.08"

# The original AUI skeleton is based on wx examples (demo)
# Also inspired by activegrid wx sample (pyide), wxpydev, pyragua, picalo, SPE,
#      pythonwin, drpython, idle

import ConfigParser

import os
import shlex
import sys
import traceback

import wx
import wx.grid
import wx.html
import wx.lib.agw.aui as aui

import images

from editor import EditorCtrl
from shell import Shell
from debugger import Debugger, EVT_DEBUG_ID
from console import ConsoleCtrl

# optional extensions that may have special dependencies (disabled if not meet)
ADDONS = []
try:
    from psp import PSPMixin
    ADDONS.append("psp")
except:
    class PSPMixin(object):
        pass
try:
    from repo import RepoMixin, RepoEvent, EVT_REPO_ID
    ADDONS.extend(["repo", "hg"])
except ImportError:
    class RepoMixin(object):
        pass

try:
    from browser import SimpleBrowserPanel
    ADDONS.append("webbrowser")
except ImportError:
    SimpleBrowserPanel = None

from web2py import Web2pyMixin
ADDONS.append("web2py")

TITLE = "ide2py %s (rad2py) [%s]" % (__version__, ', '.join(ADDONS))
CONFIG_FILE = "ide2py.ini"
REDIRECT_STDIO = False

ID_COMMENT = wx.NewId()
ID_GOTO = wx.NewId()

ID_RUN = wx.NewId()
ID_DEBUG = wx.NewId()
ID_CHECK = wx.NewId()
ID_EXEC = wx.NewId()
ID_SETARGS = wx.NewId()
ID_KILL = wx.NewId()

ID_BREAKPOINT = wx.NewId()
ID_CLEARBREAKPOINTS = wx.NewId()
ID_STEPIN = wx.NewId()
ID_STEPRETURN = wx.NewId()
ID_STEPNEXT = wx.NewId()
ID_STEPRETURN = wx.NewId()
ID_JUMP = wx.NewId()
ID_CONTINUE = wx.NewId()
ID_CONTINUETO = wx.NewId()
ID_STOP = wx.NewId()
ID_INSPECT = wx.NewId()



class PyAUIFrame(aui.AuiMDIParentFrame, Web2pyMixin, PSPMixin, RepoMixin):
    def __init__(self, parent):
        aui.AuiMDIParentFrame.__init__(self, parent, -1, title=TITLE,
            size=(800,600), style=wx.DEFAULT_FRAME_STYLE)

        #sys.excepthook  = self.ExceptHook
        
        self.children = []
        self.active_child = None        # current editing file
        self.debugging_child = None     # current debugged file
        self.debugging = False
        self.lastprogargs = ""
        self.pythonargs = ""
        self.pid = None      
        
        # tell FrameManager to manage this frame        
        self._mgr = aui.AuiManager(self)
        self.Show()
        ##self._mgr.SetManagedWindow(self)
        
        #self.SetIcon(images.GetMondrianIcon())

        # create menu
        self.menubar = wx.MenuBar()
        self.menu = {}

        file_menu = self.menu['file'] = wx.Menu()
        file_menu.Append(wx.ID_NEW, "New\tCtrl-N")
        file_menu.Append(wx.ID_OPEN, "Open File\tCtrl-O")
        file_menu.Append(wx.ID_SAVE, "Save\tCtrl-S")
        file_menu.Append(wx.ID_SAVEAS, "Save As")        
        file_menu.AppendSeparator()
        
        # and a file history
        recent_files_submenu = wx.Menu()
        self.filehistory = wx.FileHistory()
        self.filehistory.UseMenu(recent_files_submenu)
        file_menu.AppendMenu(wx.ID_FILE, "Recent Files", recent_files_submenu)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.Cleanup)
        self.Bind(wx.EVT_MENU_RANGE, self.OnFileHistory, 
                    id=wx.ID_FILE1, id2=wx.ID_FILE9)
        
        file_menu.AppendSeparator()        
        file_menu.Append(wx.ID_EXIT, "Exit")

        edit_menu = self.menu['edit'] = wx.Menu()
        edit_menu.Append(wx.ID_UNDO, "Undo\tCtrl-U")
        edit_menu.Append(wx.ID_REDO, "Redo\tCtrl-Y")
        edit_menu.AppendSeparator()
        edit_menu.Append(wx.ID_CUT, "Cut\tCtrl-X")
        edit_menu.Append(wx.ID_COPY, "Copy\tCtrl-C")
        edit_menu.Append(wx.ID_PASTE, "Paste\tCtrl-P")
        edit_menu.AppendSeparator()
        edit_menu.Append(wx.ID_FIND, '&Find\tCtrl-F', 'Find in the Demo Code')
        edit_menu.Append(wx.ID_REPLACE, "Replace\tCtrl-H", "Search and replace")
        edit_menu.AppendSeparator()
        edit_menu.Append(ID_COMMENT, 'Comment/Uncomment\tAlt-3', "")
        edit_menu.Append(ID_GOTO, "Goto Line/Regex\tCtrl-G", "")

        run_menu = self.menu['run'] = wx.Menu()
        run_menu.Append(ID_RUN, "Run in Interpreter\tShift+F5")
        run_menu.Append(ID_DEBUG, "Run in Debugger\tF5")
        run_menu.AppendSeparator()
        run_menu.Append(ID_EXEC, "Execute as an external process\tCtrl+F5")
        run_menu.Append(ID_KILL, "Kill external process\tCtrl+C")
        run_menu.AppendSeparator()
        run_menu.Append(ID_SETARGS, "Set Arguments (sys.argv)")       

        dbg_menu = self.menu['debug'] = wx.Menu()
        dbg_menu.Append(ID_STEPIN, "Step In\tF8")
        dbg_menu.Append(ID_STEPNEXT, "Step Next\tShift-F8")
        dbg_menu.Append(ID_STEPRETURN, "Step Return\tCtrl-Shift-F8")
        dbg_menu.Append(ID_CONTINUETO, "Continue up to the cursor\tCtrl-F8")
        dbg_menu.Append(ID_CONTINUE, "Continue\tF5")
        dbg_menu.Append(ID_JUMP, "Jump to instruction\tCtrl-F9")
        dbg_menu.Append(ID_STOP, "Stop")
        dbg_menu.AppendSeparator()
        dbg_menu.Append(ID_INSPECT, "Quick Inspection\tShift-F9", 
                        help="Evaluate selected text (expression) in context")
        dbg_menu.AppendSeparator()
        dbg_menu.Append(ID_BREAKPOINT, "Toggle Breakpoint\tF9")
        dbg_menu.Append(ID_CLEARBREAKPOINTS, "Clear All Breakpoint\tCtrl-Shift-F9")
        
        help_menu = self.menu['help'] = wx.Menu()
        help_menu.Append(wx.ID_ABOUT, "About...")
        
        self.menubar.Append(file_menu, "File")
        self.menubar.Append(edit_menu, "Edit")
        self.menubar.Append(run_menu, "Run")
        self.menubar.Append(dbg_menu, "Debug")
        self.menubar.Append(help_menu, "Help")
        
        self.SetMenuBar(self.menubar)

        self.statusbar = self.CreateStatusBar(2, wx.ST_SIZEGRIP)
        self.statusbar.SetStatusWidths([-2, -3])
        self.statusbar.SetStatusText("Ready", 0)
        self.statusbar.SetStatusText("Welcome To ide2py!", 1)

        # min size for the frame itself isn't completely done.
        # see the end up FrameManager::Update() for the test
        # code. For now, just hard code a frame minimum size
        self.SetMinSize(wx.Size(400, 300))

        # create some toolbars

        # aui tool_id, label, bitmap, short_help_string='', kind=0)
        # wx  id, bitmap, shortHelpString='', longHelpString='', isToggle=
        self.toolbar = aui.AuiToolBar(self, -1, wx.DefaultPosition, wx.DefaultSize,
                         wx.TB_FLAT | wx.TB_NODIVIDER)
        tsize = (16, 16)
        self.toolbar.SetToolBitmapSize(wx.Size(*tsize))

        GetBmp = lambda id: wx.ArtProvider.GetBitmap(id, wx.ART_TOOLBAR, tsize)
        self.toolbar.AddSimpleTool(wx.ID_NEW, "New", GetBmp(wx.ART_NEW))
        self.toolbar.AddSimpleTool(wx.ID_OPEN, "Open", GetBmp(wx.ART_FILE_OPEN))
        self.toolbar.AddSimpleTool(wx.ID_SAVE, "Save", GetBmp(wx.ART_FILE_SAVE))
        self.toolbar.AddSimpleTool(wx.ID_SAVEAS, "Save As...", GetBmp(wx.ART_FILE_SAVE_AS))
        self.toolbar.AddSimpleTool(wx.ID_PRINT, "Print", GetBmp(wx.ART_PRINT))
        self.toolbar.AddSeparator()
        self.toolbar.AddSimpleTool(wx.ID_UNDO, "Undo", GetBmp(wx.ART_UNDO))
        self.toolbar.AddSimpleTool(wx.ID_REDO, "Redo", GetBmp(wx.ART_REDO))
        self.toolbar.AddSeparator()
        self.toolbar.AddSimpleTool(wx.ID_CUT, "Cut", GetBmp(wx.ART_CUT))
        self.toolbar.AddSimpleTool(wx.ID_COPY, "Copy", GetBmp(wx.ART_COPY))
        self.toolbar.AddSimpleTool(wx.ID_PASTE, "Paste", GetBmp(wx.ART_PASTE))
        self.toolbar.AddSeparator()
        self.toolbar.AddSimpleTool(wx.ID_FIND, "Find", GetBmp(wx.ART_FIND))
        self.toolbar.AddSimpleTool(wx.ID_REPLACE, "Replace", GetBmp(wx.ART_FIND_AND_REPLACE))
        self.toolbar.AddSeparator()
        self.toolbar.AddSimpleTool(wx.ID_ABOUT, "About", GetBmp(wx.ART_HELP))
        self.toolbar.AddSeparator()               
        self.toolbar.AddSimpleTool(ID_RUN, "Run", images.GetRunningManBitmap())
        self.toolbar.SetToolDropDown(ID_RUN, True)
        self.toolbar.AddSimpleTool(ID_CHECK, "Check", images.ok_16.GetBitmap())

        self.toolbar.Realize()

        menu_handlers = [
            (wx.ID_NEW, self.OnNew),
            (wx.ID_OPEN, self.OnOpen),
            (wx.ID_SAVE, self.OnSave),
            (wx.ID_SAVEAS, self.OnSaveAs),
            (ID_CHECK, self.OnCheck),
            (ID_RUN, self.OnRun),
            (ID_EXEC, self.OnExecute),
            (ID_SETARGS, self.OnSetArgs),
            (ID_KILL, self.OnKill),
            (ID_DEBUG, self.OnDebugCommand),
            #(wx.ID_PRINT, self.OnPrint),
            (wx.ID_FIND, self.OnEditAction),
            (wx.ID_REPLACE, self.OnEditAction),
            (wx.ID_CUT, self.OnEditAction),
            (wx.ID_COPY, self.OnEditAction),
            (wx.ID_PASTE, self.OnEditAction),
            (wx.ID_ABOUT, self.OnEditAction),
            (ID_COMMENT, self.OnEditAction),
            (ID_GOTO, self.OnEditAction),
            (ID_BREAKPOINT, self.OnEditAction),
            (ID_CLEARBREAKPOINTS, self.OnEditAction),
         ]
        for menu_id, handler in menu_handlers:
            self.Bind(wx.EVT_MENU, handler, id=menu_id)

        self.Bind(aui.EVT_AUITOOLBAR_TOOL_DROPDOWN, self.OnDropDownRun, id=ID_RUN)

        # debugging facilities:

        self.toolbardbg = aui.AuiToolBar(self, -1, 
                            style=wx.TB_FLAT | wx.TB_NODIVIDER)
        self.toolbardbg.SetToolBitmapSize(wx.Size(*tsize))

        self.toolbardbg.AddSimpleTool(ID_STEPIN, "Step", images.GetStepInBitmap())
        self.toolbardbg.AddSimpleTool(ID_STEPNEXT, "Next", images.GetStepReturnBitmap())
        self.toolbardbg.AddSimpleTool(ID_CONTINUE, "Continue", images.GetContinueBitmap())
        self.toolbardbg.AddSimpleTool(ID_STOP, "Quit", images.GetStopBitmap())
        self.toolbardbg.AddSimpleTool(ID_INSPECT, "Inspect", images.GetAddWatchBitmap())
        self.toolbardbg.Realize()

        for menu_id in [ID_STEPIN, ID_STEPRETURN, ID_STEPNEXT, ID_STEPRETURN,
                        ID_CONTINUE, ID_STOP, ID_INSPECT, ID_JUMP, ID_CONTINUETO]:
            self.Bind(wx.EVT_MENU, self.OnDebugCommand, id=menu_id)

        self.debugger = Debugger(self)

        self._mgr.AddPane(self.toolbar, aui.AuiPaneInfo().Name("toolbar").
                          ToolbarPane().Top().Position(0))

        self._mgr.AddPane(self.toolbardbg, aui.AuiPaneInfo().Name("debug").
                          ToolbarPane().Top().Position(1))
                      
        self.browser = self.CreateBrowserCtrl()
        if self.browser:
            self._mgr.AddPane(self.browser, aui.AuiPaneInfo().Name("browser").
                          Caption("Simple Browser").Right().CloseButton(True))

        self.shell = Shell(self)
        self._mgr.AddPane(self.shell, aui.AuiPaneInfo().Name("shell").
                          Caption("Shell").
                          Bottom().Layer(1).Position(1).CloseButton(True))

        self.console = ConsoleCtrl(self)
        self._mgr.AddPane(self.console, aui.AuiPaneInfo().Name("console").
                          Caption("Console (stdio)").
                          Bottom().Layer(1).Position(2).CloseButton(True))

        # "commit" all changes made to FrameManager   
        self._mgr.Update()

        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_CLOSE, self.OnClose)

        self.Bind(wx.EVT_MENU, self.OnExit, id=wx.ID_EXIT)
        self.Bind(wx.EVT_MENU, self.OnAbout, id=wx.ID_ABOUT)

        # Connect to debugging events
        self.Connect(-1, -1, EVT_DEBUG_ID, self.GotoFileLine)
        
        PSPMixin.__init__(self)
        RepoMixin.__init__(self)

        # Restore configuration
        cfg_aui = wx.GetApp().get_config("AUI")
        
        if cfg_aui.get('maximize', True):
            self.Maximize()

        # Restore a perspective layout. WARNING: all panes must have a name!
        perspective = cfg_aui.get('perspective', "")
        if perspective:
            self._mgr.Update()
            self._mgr.LoadPerspective(perspective)

        # restore file history config:
        cfg_history = wx.GetApp().get_config("HISTORY")
        for filenum in range(9,-1,-1):
            filename = cfg_history.get('file_%s' % filenum, "")
            if filename:
                self.filehistory.AddFileToHistory(filename)

        # redirect all inputs and outputs to own console window
        # WARNING: Shell takes over raw_input (TODO: Fix?)
        if REDIRECT_STDIO:
            sys.stdin = sys.stdout = sys.stderr = self.console

        # web2py initialization (on own thread to enable debugger)
        Web2pyMixin.__init__(self)

    def Cleanup(self, *args):
        if 'repo' in ADDONS:
            self.RepoMixinCleanup()
        # A little extra cleanup is required for the FileHistory control
        if hasattr(self, "filehistory"):
            # save recent file history in config file
            for filenum in range(0,10):
                filename = self.filehistory.GetHistoryFile(filenum)
                wx.GetApp().config.set('HISTORY', 'file_%s' % filenum, filename)
            del self.filehistory
            #self.recent_files_submenu.Destroy() # warning: SEGV!

    def OnClose(self, event):
        # Save current perspective layout. WARNING: all panes must have a name! 
        perspective = self._mgr.SavePerspective()
        wx.GetApp().config.set('AUI', 'perspective', perspective)
        self._mgr.UnInit()
        del self._mgr
        self.Destroy()


    def OnExit(self, event):
        self.Close()

    def OnAbout(self, event):
        msg = "%s - Licenced under the GPLv3\n"  % TITLE + \
              "A modern, minimalist, cross-platform, complete and \n" + \
              "totally Integrated Development Environment\n" + \
              "for Rapid Application Development in Python \n" + \
              "guided by the Personal Software Process (TM).\n" + \
              "(c) Copyright 2011, Mariano Reingart\n" + \
              "Inspired by PSP Process Dashboard and several Python IDEs. \n" + \
              "Some code was based on wxPython demos and other projects\n" + \
              "(see sources or http://code.google.com/p/rad2py/)"
        dlg = wx.MessageDialog(self, msg, TITLE,
                               wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()        

    def GetDockArt(self):
        return self._mgr.GetArtProvider()

    def DoUpdate(self):
        self._mgr.Update()

    def OnEraseBackground(self, event):
        event.Skip()

    def OnSize(self, event):
        event.Skip()

    def OnNew(self, event):
        child = AUIChildFrame(self, "")
        child.Show()
        self.children.append(child)
        return child

    def OnOpen(self, event):
        dlg = wx.FileDialog(
            self, message="Choose a file",
            defaultDir=os.getcwd(), 
            defaultFile="hola.py",
            wildcard="Python Files (*.py)|*.py",
            style=wx.OPEN 
            )
        
        if dlg.ShowModal() == wx.ID_OK:
            # This returns a Python list of files that were selected.
            filename = dlg.GetPaths()[0]        
            self.DoOpen(filename)
            # add it to the history
            self.filehistory.AddFileToHistory(filename)

        dlg.Destroy()

    def OnFileHistory(self, evt):
        # get the file based on the menu ID
        filenum = evt.GetId() - wx.ID_FILE1
        filepath = self.filehistory.GetHistoryFile(filenum)
        self.DoOpen(filepath)
        # add it back to the history so it will be moved up the list
        self.filehistory.AddFileToHistory(filepath)

    def DoOpen(self, filename):
        found = [child for child in self.children if child.GetFilename()==filename]
        if not found:
            child = AUIChildFrame(self, filename)
            child.Show()
            self.children.append(child)
        else:
            child = found[0]
            child.Activate()
            child.SetFocus()
        return child

    def OnSave(self, event):
        if self.active_child:
            self.active_child.OnSave(event)

    def OnSaveAs(self, event):
        if self.active_child:
            self.active_child.OnSaveAs(event)

    def OnRun(self, event, debug=False):
        if self.active_child:
            # add the path of this script so we can import things
            syspath = [ os.path.split(self.active_child.GetFilename())[0] ]            
            # preserve current directory
            cwd = os.getcwd()
            try:
                # change to script directory
                os.chdir(syspath[0])                 
                # create a code objectbject and run it in the main thread
                code = self.active_child.GetCodeObject()
                filename = os.path.split(self.active_child.GetFilename())[1]
                msg = not debug and "Running" or "Debugging"
                self.statusbar.SetStatusText("%s: %s" % (msg, filename), 1)
                if code:
                    # set program arguments (workaround shlex unicode bug)
                    args = self.lastprogargs.encode("ascii", "ignore")
                    sys.argv = [filename] + shlex.split(args)
                    self.shell.RunScript(code, syspath, debug and self.debugger, self.console)
                self.statusbar.SetStatusText("", 1)
            finally:
                os.chdir(cwd)

    def OnSetArgs(self, event):
        dlg = wx.TextEntryDialog(self, 'Enter program arguments (sys.argv):', 
            'Set Arguments', self.lastprogargs)
        if dlg.ShowModal() == wx.ID_OK:
            self.lastprogargs = dlg.GetValue()
        dlg.Destroy()
    
    def OnExecute(self, event):
        if self.active_child and not self.console.process:
            filename = self.active_child.GetFilename()
            cdir, filen = os.path.split(filename)
            cwd = os.getcwd()
            try:
                os.chdir(cdir)
                largs = self.lastprogargs and ' ' + self.lastprogargs or ""
                if wx.Platform == '__WXMSW__':
                    pythexec = sys.prefix.replace("\\", "/") + "/pythonw.exe"
                    filename = filename.replace("\\", "/")
                else:
                    pythexec = sys.executable
                self.Execute((pythexec + " -u " +  self.pythonargs + ' "' + 
                    filename + '"'  + largs), filen)
            except Exception, e:
                raise
                #ShowMessage("Error Setting current directory for Execute")
            finally:
                os.chdir(cwd)
    
    def OnKill(self, event):
        if self.console.process:
            self.console.process.Kill(self.console.process.pid, wx.SIGKILL)

    def Execute(self, command, filename, redin="", redout="", rederr=""):
        "Execute a command and redirect input/output/error to internal console"
        statusbar = self.statusbar
        console = self.console
        statusbar.SetStatusText("Executing %s" % command, 1)
        
        class MyProcess(wx.Process):
            "Custom Process Class to handle OnTerminate event method"

            def OnTerminate(self, pid, status):
                "Clean up on termination (prevent SEGV!)"
                console.process = None
                statusbar.SetStatusText("Terminated: %s!" % filename, 0)
                statusbar.SetStatusText("", 1)
        
        process = console.process = MyProcess(self)
        process.Redirect()
        flags = wx.EXEC_ASYNC
        if wx.Platform == '__WXMSW__':
            flags |= wx.EXEC_NOHIDE
        self.pid = process.pid = wx.Execute(command, flags, process)
        console.inputstream = process.GetInputStream()
        console.errorstream = process.GetErrorStream()
        console.outputstream = process.GetOutputStream()
        console.process.redirectOut = redout
        console.process.redirectErr = rederr
        console.SetFocus()


    def OnDropDownRun(self, event):
        if event.IsDropDownClicked():
            tb = event.GetEventObject()
            tb.SetToolSticky(event.GetId(), True)

            # create the popup menu
            menuPopup = self.menu['run'] 

            # line up our menu with the button
            rect = tb.GetToolRect(event.GetId())
            pt = tb.ClientToScreen(rect.GetBottomLeft())
            pt = self.ScreenToClient(pt)
            self.PopupMenu(menuPopup, pt)
            # make sure the button is "un-stuck"
            tb.SetToolSticky(event.GetId(), False)
           
    def GotoFileLine(self, event=None, running=True):
        if event and running:
            filename, lineno = event.data
        elif not running:
            filename, lineno, offset = event
        # first, clean all current debugging markers
        for child in self.children:
            if running:
                child.SynchCurrentLine(None)
                self.debugging_child = None
        # then look for the file being debugged
        if event:
            child = self.DoOpen(filename)
            if child:
                if running:
                    child.SynchCurrentLine(lineno)
                    self.debugging_child = child
                else:
                    child.GotoLineOffset(lineno, offset)
                    
    def OnDebugCommand(self, event):
        event_id = event.GetId()

        # Not debbuging?, set temp breakpoint to be hit on first run!
        if event_id == ID_CONTINUETO and not self.debugging_child and self.active_child:
            lineno = self.active_child.GetCurrentLine()
            filename = self.active_child.GetFilename()
            self.debugger.SetBreakpoint(filename, lineno, temporary=1)

        # start debugger (if not running):
        if event_id == ID_DEBUG or not self.debugging:
            self.debugging = True
            # should it open debugger inmediatelly or continue?
            self.debugger.start_continue = event_id in (ID_CONTINUE, ID_CONTINUETO)
            self.OnRun(event, debug=True)
            self.debugging = False
            # clean running indication
            self.GotoFileLine()
        elif event_id == ID_STEPIN:
            self.debugger.Step()
        elif event_id == ID_STEPNEXT:
            self.debugger.Next()
        elif event_id == ID_STEPRETURN:
            self.debugger.StepReturn()
        elif event_id == ID_CONTINUE:
            self.GotoFileLine()
            self.debugger.Continue()
        elif event_id == ID_STOP:
            self.debugger.Quit()
        elif event_id == ID_INSPECT and self.active_child:
            # Eval selected text (expression) in debugger running context
            arg = self.active_child.GetSelectedText()
            val = self.debugger.inspect(arg)
            dlg = wx.MessageDialog(self, "Expression: %s\nValue: %s" % (arg, val), 
                                   "Debugger Quick Inspection",
                                   wx.ICON_INFORMATION)
            dlg.ShowModal()
            dlg.Destroy()
        elif event_id == ID_JUMP and self.debugging_child:
            # change actual line number (if possible)
            lineno = self.debugging_child.GetCurrentLine()
            if self.debugger.Jump(lineno) is not False:
                self.debugging_child.SynchCurrentLine(lineno)
            else:
                print "Fail!"
        elif event_id == ID_CONTINUETO and self.debugging_child:
            # Continue execution until we reach selected line (temp breakpoint)
            lineno = self.debugging_child.GetCurrentLine()
            filename = self.debugging_child.GetFilename()
            self.debugger.SetBreakpoint(filename, lineno, temporary=1)
            self.debugger.Continue()

    def OnCheck(self, event):
        # TODO: separate checks and tests, add reviews and diffs...
        if self.active_child:
            import checker
            for error in checker.check(self.active_child.GetFilename()):
                self.NotifyDefect(**error)
            import tester
            for error in tester.test(self.active_child.GetFilename()):
                self.NotifyDefect(**error)

    def CreateTextCtrl(self):
        text = ("This is text box")
        return wx.TextCtrl(self,-1, text, wx.Point(0, 0), wx.Size(150, 90),
                           wx.NO_BORDER | wx.TE_MULTILINE)

    def CreateBrowserCtrl(self):
        if SimpleBrowserPanel:
            return SimpleBrowserPanel(self)

    def CreateGrid(self):
        grid = wx.grid.Grid(self, -1, wx.Point(0, 0), wx.Size(150, 250),
                            wx.NO_BORDER | wx.WANTS_CHARS)
        grid.CreateGrid(50, 20)
        return grid


    def CreateHTMLCtrl(self):
        ctrl = wx.html.HtmlWindow(self, -1, wx.DefaultPosition, wx.Size(400, 300))
        if "gtk2" in wx.PlatformInfo:
            ctrl.SetStandardFonts()
        ctrl.SetPage("hola!")
        return ctrl    
        
    def OnEditAction(self, event):
        if self.active_child:
            self.active_child.OnEditAction(event)

    def ExceptHook(self, type, value, trace): 
        exc = traceback.format_exception(type, value, trace) 
        for e in exc: wx.LogError(e) 
        wx.LogError(u'Unhandled Error: %s: %s'%(str(type), unicode(value)))
        # TODO: automatic defect classification
        tb = traceback.extract_tb(trace)
        if tb:
            filename, lineno, function_name, text = tb[-1]
            self.NotifyDefect(description=str(e), type="60", filename=filename, lineno=lineno, offset=1)
        # enter post-mortem debugger
        self.debugger.pm()

    def NotifyRepo(self, filename, action="", status=""):
        if 'repo' in ADDONS:
            wx.PostEvent(self, RepoEvent(filename, action, status))


class AUIChildFrame(aui.AuiMDIChildFrame):

    def __init__(self, parent, filename):
        aui.AuiMDIChildFrame.__init__(self, parent, -1,
                                         title="")  
        app = wx.GetApp()
        
        self.editor = EditorCtrl(self,-1, filename=filename,    
                                 debugger=parent.debugger,
                                 lang="python", 
                                 cfg=app.get_config("EDITOR"),
                                 cfg_styles=app.get_config("STC.PY"))
        sizer = wx.BoxSizer()
        sizer.Add(self.editor, 1, wx.EXPAND)
        self.SetSizer(sizer)        
        wx.CallAfter(self.Layout)

        self.parent = parent
        self.Bind(wx.EVT_SET_FOCUS, self.OnFocus)   # window focused
        self.Bind(wx.EVT_ACTIVATE, self.OnFocus)   # window focused
        self.OnFocus(None) # emulate initial focus
 
    def OnFocus(self, event):
        self.parent.active_child = self

    def OnSave(self, event):
        self.editor.OnSave(event)

    def OnSaveAs(self, event):
        self.editor.OnSaveAs(event)

    def OnEditAction(self, event):
        handlers = {
            wx.ID_FIND: self.editor.DoFind,
            wx.ID_REPLACE: self.editor.DoReplace,
            wx.ID_COPY: self.editor.DoBuiltIn,
            wx.ID_PASTE: self.editor.DoBuiltIn,
            wx.ID_CUT: self.editor.DoBuiltIn,
            ID_BREAKPOINT: self.editor.ToggleBreakpoint,
            ID_CLEARBREAKPOINTS: self.editor.ClearBreakpoints,
            ID_COMMENT: self.editor.ToggleComment,
            ID_GOTO: self.editor.DoGoto,
            }
        handlers[event.GetId()](event)

    def GetFilename(self):
        return self.editor.filename

    def GetCodeObject(self,):
        return self.editor.GetCodeObject()

    def GetSelectedText(self,):
        return self.editor.GetSelectedText()

    def GetCurrentLine(self):
        return self.editor.GetCurrentLine() + 1
        
    def SynchCurrentLine(self, lineno):
        if lineno:
            self.SetFocus()
        self.editor.SynchCurrentLine(lineno)

    def GotoLineOffset(self, lineno, offset):
        if lineno:
            self.SetFocus()
            self.editor.GotoLineOffset(lineno, offset)

    def NotifyDefect(self, *args, **kwargs):
        self.parent.NotifyDefect(*args, **kwargs)
    
    def NotifyRepo(self, *args, **kwargs):
        self.parent.NotifyRepo(*args, **kwargs)


# Configuration Helper to Encapsulate common config read scenarios:
class FancyConfigDict(object):
    "Dict-like shortcut to a configuration  parser section with proper defaults"
    
    def __init__(self, section, configparser):
        self.section = section
        self.configparser = configparser
        
    def get(self, option, default=None):
        "return an option, or default if not found (convert to default type)"
        try:
            section = self.section
            if isinstance(default, bool):
                val = self.configparser.getboolean(section, option)
            elif isinstance(default, int):
                val = self.configparser.getint(section, option)
            elif isinstance(default, int):
                val = self.configparser.getint(section, option)
            else:
                val = self.configparser.get(section, option, raw=True)
        except ConfigParser.Error:
            val = default
        return val

    def items(self):
        return self.configparser.items(self.section, raw=True)


class MainApp(wx.App):

    def OnInit(self):
        self.config = ConfigParser.ConfigParser()
        # read default configuration
        self.config.read("ide2py.ini.dist")
        # merge user custom configuration
        self.config.read(CONFIG_FILE)
        if not self.config.sections():
            raise RuntimeError("No configuration found, use ide2py.ini.dist!")
        self.main_frame = PyAUIFrame(None)
        self.main_frame.Show()
        return True

    def OnExit(self):
        self.write_config()

    def get_config(self, section):
        return FancyConfigDict(section, self.config)

    def write_config(self):
        self.config.write(open(CONFIG_FILE, "w"))


if __name__ == '__main__':
    # start main app, avoid wx redirection on windows
    app = MainApp(redirect=False)
    app.MainLoop()


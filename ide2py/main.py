#!/usr/bin/env python
# coding:utf-8

"Pythonic Integrated Development Environment for Rapid Application Development"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"
__version__ = "0.03"

# The original AUI skeleton is based on wx examples (demo)
# Also inspired by activegrid wx sample (pyide), wxpydev, pyragua, picalo, SPE,
#      pythonwin, drpython, idle

import ConfigParser

import os
import sys
import traceback

import wx
import wx.grid
import wx.html
import wx.lib.agw.aui as aui

import images

from browser import SimpleBrowserPanel
from editor import EditorCtrl
from shell import Shell
from debugger import Debugger, EVT_DEBUG_ID
from console import ConsoleCtrl
from psp import PSPMixin

try:
    from repo import RepoMixin, RepoEvent, EVT_REPO_ID
except ImportError:
    RepoMixin = object

TITLE = "ide2py w/PSP - v%s (rad2py)" % __version__
CONFIG_FILE = "ide2py.ini"
REDIRECT_STDIO = False


class PyAUIFrame(aui.AuiMDIParentFrame, PSPMixin, RepoMixin):
    def __init__(self, parent):
        aui.AuiMDIParentFrame.__init__(self, parent, -1, title=TITLE,
            size=(800,600), style=wx.DEFAULT_FRAME_STYLE)

        #sys.excepthook  = self.ExceptHook
        
        self.children = {}
        self.active_child = None
        
        # tell FrameManager to manage this frame        
        self._mgr = aui.AuiManager(self)
        self.Show()
        ##self._mgr.SetManagedWindow(self)
        
        #self.SetIcon(images.GetMondrianIcon())

        # create menu
        self.menubar = wx.MenuBar()
        self.menu = {}

        file_menu = self.menu['file'] = wx.Menu()
        file_menu.Append(wx.ID_NEW, "New")
        file_menu.Append(wx.ID_OPEN, "Open")
        file_menu.Append(wx.ID_SAVE, "Save")
        file_menu.Append(wx.ID_SAVEAS, "Save As")        
        file_menu.AppendSeparator()        
        file_menu.Append(wx.ID_EXIT, "Exit")

        edit_menu = self.menu['edit'] = wx.Menu()
        edit_menu.Append(wx.ID_UNDO, "Undo")
        edit_menu.Append(wx.ID_REDO, "Redo")
        edit_menu.AppendSeparator()
        edit_menu.Append(wx.ID_CUT, "Cut")
        edit_menu.Append(wx.ID_COPY, "Copy")
        edit_menu.Append(wx.ID_PASTE, "Paste")
        edit_menu.AppendSeparator()        
        edit_menu.Append(wx.ID_FIND, "Find")
        edit_menu.Append(wx.ID_REPLACE, "Replace")
          
        help_menu = self.menu['help'] = wx.Menu()
        help_menu.Append(wx.ID_ABOUT, "About...")
        
        self.menubar.Append(file_menu, "File")
        self.menubar.Append(edit_menu, "Edit")
        self.menubar.Append(help_menu, "Help")
        
        self.SetMenuBar(self.menubar)

        self.statusbar = self.CreateStatusBar(2, wx.ST_SIZEGRIP)
        self.statusbar.SetStatusWidths([-2, -3])
        self.statusbar.SetStatusText("Ready", 0)
        self.statusbar.SetStatusText("Welcome To wxPython!", 1)

        # min size for the frame itself isn't completely done.
        # see the end up FrameManager::Update() for the test
        # code. For now, just hard code a frame minimum size
        self.SetMinSize(wx.Size(400, 300))

        # create some toolbars

        self.toolbar = wx.ToolBar(self, -1, wx.DefaultPosition, wx.DefaultSize,
                         wx.TB_FLAT | wx.TB_NODIVIDER)
        tsize = (16, 16)
        self.toolbar.SetToolBitmapSize(wx.Size(*tsize))

        GetBmp = wx.ArtProvider.GetBitmap
        self.toolbar.AddSimpleTool(
            wx.ID_NEW, GetBmp(wx.ART_NEW, wx.ART_TOOLBAR, tsize), "New")
        self.toolbar.AddSimpleTool(
            wx.ID_OPEN, GetBmp(wx.ART_FILE_OPEN, wx.ART_TOOLBAR, tsize), "Open")
        self.toolbar.AddSimpleTool(
            wx.ID_SAVE, GetBmp(wx.ART_FILE_SAVE, wx.ART_TOOLBAR, tsize), "Save")
        self.toolbar.AddSimpleTool(
            wx.ID_SAVEAS, GetBmp(wx.ART_FILE_SAVE_AS, wx.ART_TOOLBAR, tsize),
            "Save As...")
        self.toolbar.AddSimpleTool(
            wx.ID_PRINT, GetBmp(wx.ART_PRINT, wx.ART_TOOLBAR, tsize), "Print")
        #-------
        self.toolbar.AddSeparator()
        self.toolbar.AddSimpleTool(
            wx.ID_UNDO, GetBmp(wx.ART_UNDO, wx.ART_TOOLBAR, tsize), "Undo")
        self.toolbar.AddSimpleTool(
            wx.ID_REDO, GetBmp(wx.ART_REDO, wx.ART_TOOLBAR, tsize), "Redo")
        self.toolbar.AddSeparator()
        #-------
        self.toolbar.AddSimpleTool(
            wx.ID_CUT, GetBmp(wx.ART_CUT, wx.ART_TOOLBAR, tsize), "Cut")
        self.toolbar.AddSimpleTool(
            wx.ID_COPY, GetBmp(wx.ART_COPY, wx.ART_TOOLBAR, tsize), "Copy")
        self.toolbar.AddSimpleTool(
            wx.ID_PASTE, GetBmp(wx.ART_PASTE, wx.ART_TOOLBAR, tsize), "Paste")
        self.toolbar.AddSeparator()
        self.toolbar.AddSimpleTool(
            wx.ID_FIND, GetBmp(wx.ART_FIND, wx.ART_TOOLBAR, tsize), "Find")
        self.toolbar.AddSimpleTool(
            wx.ID_REPLACE, GetBmp(wx.ART_FIND_AND_REPLACE, wx.ART_TOOLBAR, tsize), "Replace")
        self.toolbar.AddSeparator()
        self.toolbar.AddSimpleTool(
            wx.ID_ABOUT, GetBmp(wx.ART_HELP, wx.ART_TOOLBAR, tsize), "About")

        self.toolbar.AddSeparator()
        
        self.ID_RUN = wx.NewId()
        self.ID_DEBUG = wx.NewId()
        self.ID_CHECK = wx.NewId()

        self.ID_STEPIN = wx.NewId()
        self.ID_STEPRETURN = wx.NewId()
        self.ID_STEPNEXT = wx.NewId()
        self.ID_CONTINUE = wx.NewId()
        self.ID_STOP = wx.NewId()
        
        self.toolbar.AddSimpleTool(
            self.ID_RUN, images.GetRunningManBitmap(), "Run")
        self.toolbar.AddSimpleTool(
            self.ID_DEBUG, images.GetDebuggingBitmap(), "Debug")
        self.toolbar.AddSimpleTool(
            self.ID_CHECK, images.ok_16.GetBitmap(), "Check")

        self.toolbar.Realize()

        menu_handlers = [
            (wx.ID_NEW, self.OnNew),
            (wx.ID_OPEN, self.OnOpen),
            (wx.ID_SAVE, self.OnSave),
            (wx.ID_SAVEAS, self.OnSaveAs),
            (self.ID_CHECK, self.OnCheck),
            (self.ID_RUN, self.OnRun),
            (self.ID_DEBUG, self.OnDebug),
            #(wx.ID_PRINT, self.OnPrint),
            #(wx.ID_FIND, self.OnFind),
            #(wx.ID_REPLACE, self.OnModify),
            #(wx.ID_CUT, self.OnCut),
            #(wx.ID_COPY, self.OnCopy),
            #(wx.ID_PASTE, self.OnPaste),
            #(wx.ID_ABOUT, self.OnAbout),
        ]
        for menu_id, handler in menu_handlers:
            self.Bind(wx.EVT_MENU, handler, id=menu_id)
    
        # debugging facilities:

        self.toolbardbg = wx.ToolBar(self, -1, wx.DefaultPosition, wx.DefaultSize,
                         wx.TB_FLAT | wx.TB_NODIVIDER)
        tsize = (16, 16)
        self.toolbardbg.SetToolBitmapSize(wx.Size(*tsize))

        self.toolbardbg.AddSimpleTool(
            self.ID_DEBUG, images.GetBreakBitmap(), "Break")
        self.toolbardbg.AddSimpleTool(
            self.ID_STEPIN, images.GetStepInBitmap(), "Step")
        self.toolbardbg.AddSimpleTool(
            self.ID_STEPNEXT, images.GetStepReturnBitmap(), "Next")
        self.toolbardbg.AddSimpleTool(
            self.ID_CONTINUE, images.GetContinueBitmap(), "Continue")
        self.toolbardbg.AddSimpleTool(
            self.ID_STOP, images.GetStopBitmap(), "Quit")
        self.toolbardbg.AddSimpleTool(
            self.ID_DEBUG, images.GetAddWatchBitmap(), "AddWatch")            
        self.toolbardbg.AddSimpleTool(
            self.ID_DEBUG, images.GetCloseBitmap(), "Close")
        self.toolbardbg.Realize()

        for menu_id in [self.ID_STEPIN, self.ID_STEPRETURN, self.ID_STEPNEXT,
                        self.ID_CONTINUE, self.ID_STOP]:
            self.Bind(wx.EVT_MENU, self.OnDebugCommand, id=menu_id)

        self.debugger = Debugger(self)

        # add a bunch of panes                      
        self._mgr.AddPane(self.toolbar, aui.AuiPaneInfo().Name("toolbar").
                          ToolbarPane().Top().Position(0))

        self._mgr.AddPane(self.toolbardbg, aui.AuiPaneInfo().Name("debug").
                          ToolbarPane().Top().Position(1))
                      
        self.browser = self.CreateBrowserCtrl()
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

        # Show How To Use The Closing Panes Event
        self.Bind(aui.EVT_AUI_PANE_CLOSE, self.OnPaneClose)
        
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

        # redirect all inputs and outputs to own console window
        # WARNING: Shell takes over raw_input (TODO: Fix?)
        if REDIRECT_STDIO:
            sys.stdin = sys.stdout = sys.stderr = self.console

        
    def OnPaneClose(self, event):

        caption = event.GetPane().caption

        if caption in ["Tree Pane", "Dock Manager Settings", "Fixed Pane"]:
            msg = "Are You Sure You Want To Close This Pane?"
            dlg = wx.MessageDialog(self, msg, "AUI Question",
                                   wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)

            if dlg.ShowModal() in [wx.ID_NO, wx.ID_CANCEL]:
                event.Veto()
            dlg.Destroy()


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
            
        dlg.Destroy()
   
    def DoOpen(self, filename):
        if filename not in self.children:
            child = AUIChildFrame(self, filename)
            child.Show()
            self.children[filename] = child
        else:
            child = self.children[filename]
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
            syspath = [ os.path.split(self.active_child.filename)[0] ]  
     
            # create a code object and run it in the main thread
            code = self.active_child.GetCodeObject()
            if code:         
                self.shell.RunScript(code, syspath, debug and self.debugger, self.console)

    def OnDebug(self, event):
        self.OnRun(event, debug=True)
        self.GotoFileLine()
            
    def GotoFileLine(self, event=None, running=True):
        if event and running:
            filename, lineno = event.data
        elif not running:
            filename, lineno, offset = event
        # first, clean all current debugging markers
        for child in self.children.values():
            if running:
                child.SynchCurrentLine(None)
        # then look for the file being debugged
        if event:
            child = self.DoOpen(filename)
            if child:
                if running:
                    child.SynchCurrentLine(lineno)
                else:
                    child.GotoLineOffset(lineno, offset)
                    
    def OnDebugCommand(self, event):
        event_id = event.GetId()
        if event_id == self.ID_STEPIN:
            self.debugger.Step()
        elif event_id == self.ID_STEPNEXT:
            self.debugger.Next()
        elif event_id == self.ID_STEPRETURN:
            self.debugger.StepReturn()
        elif event_id == self.ID_CONTINUE:
            self.debugger.Continue()
        elif event_id == self.ID_STOP:
            self.debugger.Quit()
            self.GotoFileLine()

    def OnCheck(self, event):
        # TODO: separate checks and tests, add reviews and diffs...
        if self.active_child:
            import checker
            for error in checker.check(self.active_child.filename):
                self.NotifyDefect(**error)
            import tester
            for error in tester.test(self.active_child.filename):
                self.NotifyDefect(**error)

    def CreateTextCtrl(self):
        text = ("This is text box")
        return wx.TextCtrl(self,-1, text, wx.Point(0, 0), wx.Size(150, 90),
                           wx.NO_BORDER | wx.TE_MULTILINE)

    def CreateBrowserCtrl(self):
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
        if RepoMixin is not object:
            wx.PostEvent(self, RepoEvent(filename, action, status))


class AUIChildFrame(aui.AuiMDIChildFrame):

    def __init__(self, parent, filename):
        aui.AuiMDIChildFrame.__init__(self, parent, -1,
                                         title="")  
        app = wx.GetApp()
        
        self.filename = filename     
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

    def GetCodeObject(self,):
        return self.editor.GetCodeObject()

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
        self.config.read(CONFIG_FILE)
        if not self.config.sections():
            raise RuntimeError("No hay configuracion!")
        self.aui_frame = PyAUIFrame(None)
        self.aui_frame.Show()
        return True

    def OnExit(self):
        self.config.write(open(CONFIG_FILE, "w"))

    def get_config(self, section):
        return FancyConfigDict(section, self.config)


if __name__ == '__main__':
    app = MainApp()
    app.MainLoop()


#!/usr/bin/env python
# coding:utf-8

"Pythonic Integrated Development Environment for Rapid Application Development"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"
__version__ = "0.10"

# The original AUI skeleton is based on wx examples (demo)
# Also inspired by activegrid wx sample (pyide), wxpydev, pyragua, picalo, SPE,
#      pythonwin, drpython, idle

import ConfigParser
import imp
import os
import shlex
import sys
import traceback

# prevent import error in wx multiversion installs:
import wxversion
wxversion.select(["3.0", "2.8"])
   
import wx
import wx.grid
import wx.html
import wx.lib.agw.aui as aui
import wx.lib.dialogs

try:
    import wx.lib.agw.advancedsplash as advancedsplash
    import wx.lib.agw.infobar as infobar
except ImportError:
    # disable advanced splash screen
    advancedsplash = None
    if hasattr(wx, "InfoBar"):
        infobar = wx
    else:
        infobar = None

import images

from editor import EditorCtrl
from shell import Shell
from debugger import Debugger, EVT_DEBUG_ID, EVT_EXCEPTION_ID, \
                     EnvironmentPanel, StackListCtrl
from console import ConsoleCtrl
from explorer import ExplorerPanel, EVT_EXPLORE_ID
from task import TaskMixin
from gui2py import Gui2pyMixin
from database import Database

# optional extensions that may have special dependencies (disabled if not meet)
ADDONS = []
try:
    from psp import PSPMixin
    ADDONS.append("psp")
except ImportError:
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

try:
    from web2py import Web2pyMixin
    ADDONS.append("web2py")
except:
    class Web2pyMixin():
        def __init__(self): pass
    

TITLE = "ide2py %s (rad2py) [%s]" % (__version__, ', '.join(ADDONS))
CONFIG_FILE = "ide2py.ini"
REDIRECT_STDIO = False
RAD2PY_ICON = "rad2py.ico"
SPLASH_IMAGE = "splash.png"
DEBUG = False

ID_COMMENT = wx.NewId()
ID_GOTO = wx.NewId()
ID_GOTO_DEF = wx.NewId()
ID_OPEN_MODULE = wx.NewId()

ID_RUN = wx.NewId()
ID_DEBUG = wx.NewId()
ID_EXEC = wx.NewId()
ID_SETARGS = wx.NewId()
ID_KILL = wx.NewId()
ID_ATTACH = wx.NewId()

ID_BREAKPOINT = wx.NewId()
ID_ALTBREAKPOINT = wx.NewId()
ID_CLEARBREAKPOINTS = wx.NewId()
ID_STEPIN = wx.NewId()
ID_STEPRETURN = wx.NewId()
ID_STEPNEXT = wx.NewId()
ID_STEPRETURN = wx.NewId()
ID_JUMP = wx.NewId()
ID_CONTINUE = wx.NewId()
ID_CONTINUETO = wx.NewId()
ID_QUIT = wx.NewId()
ID_INTERRUPT = wx.NewId()
ID_EVAL = wx.NewId()

ID_EXPLORER = wx.NewId()
ID_DESIGNER = wx.NewId()


class PyAUIFrame(aui.AuiMDIParentFrame, PSPMixin, RepoMixin, TaskMixin,
                 Web2pyMixin, Gui2pyMixin):
    def __init__(self, parent):
        aui.AuiMDIParentFrame.__init__(self, parent, -1, title=TITLE,
            size=(800,600), style=wx.DEFAULT_FRAME_STYLE | wx.FRAME_NO_WINDOW_MENU)

        wx.GetApp().SetSplashText("Creating Main Frame")
        
        sys.excepthook  = self.ExceptHook
    
        # Set window title bar icon.
        if RAD2PY_ICON:
            self.SetIcon(wx.Icon(RAD2PY_ICON, wx.BITMAP_TYPE_ICO))
            
        self.children = []              # editors (notebooks)
        self.infobars = {}              # notifications (stackable panes)
        self.debugging_child = None     # current debugged file
        self.temp_breakpoint = None
        self.lastprogargs = ""
        self.pythonargs = '"%s"' % os.path.join(INSTALL_DIR, "qdb.py")
        self.pid = None
        
        # tell FrameManager to manage this frame        
        self._mgr = aui.AuiManager(self)
        self.Show()
        
        ##self._mgr.SetManagedWindow(self)
        
        wx.GetApp().SetSplashText("Creating Menus...")

        # create menu
        self.menubar = wx.MenuBar()
        self.menu = {}

        file_menu = self.menu['file'] = wx.Menu()
        file_menu.Append(wx.ID_NEW, "&New\tCtrl-N")
        file_menu.Append(wx.ID_OPEN, "&Open File\tCtrl-O")
        file_menu.Append(ID_OPEN_MODULE, "Open &Module\tCtrl-M")
        file_menu.Append(wx.ID_SAVE, "&Save\tCtrl-S")
        file_menu.Append(wx.ID_SAVEAS, "Save &As")
        file_menu.Append(wx.ID_CLOSE, "&Close\tCtrl-w")
        file_menu.AppendSeparator()

        file_menu.Append(ID_EXPLORER, "&Explorer\tCtrl-E",
                         "Refresh class & function browser")
        file_menu.AppendSeparator()
        
        # and a file history
        recent_files_submenu = wx.Menu()
        self.filehistory = wx.FileHistory()
        self.filehistory.UseMenu(recent_files_submenu)
        file_menu.AppendMenu(wx.ID_FILE, "Recent &Files", recent_files_submenu)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.Cleanup, self)
        self.Bind(wx.EVT_MENU_RANGE, self.OnFileHistory, 
                    id=wx.ID_FILE1, id2=wx.ID_FILE9)
        
        file_menu.AppendSeparator()        
        file_menu.Append(wx.ID_EXIT, "&Exit")

        edit_menu = self.menu['edit'] = wx.Menu()
        edit_menu.Append(wx.ID_UNDO, "&Undo\tCtrl-U")
        edit_menu.Append(wx.ID_REDO, "&Redo\tCtrl-Y")
        edit_menu.AppendSeparator()
        edit_menu.Append(wx.ID_CUT, "Cu&t\tShift-Delete")
        edit_menu.Append(wx.ID_COPY, "&Copy\tCtrl-Insert")
        edit_menu.Append(wx.ID_PASTE, "&Paste\tShift-Insert")
        edit_menu.AppendSeparator()
        edit_menu.Append(wx.ID_FIND, '&Find\tCtrl-F', 'Find in the Demo Code')
        edit_menu.Append(wx.ID_REPLACE, "&Replace\tCtrl-H", "Search and replace")
        edit_menu.AppendSeparator()
        edit_menu.Append(ID_COMMENT, 'Comment/Uncomment\tAlt-3', "")
        edit_menu.Append(ID_GOTO, "&Goto Line/Regex\tCtrl-G", "")
        edit_menu.Append(ID_GOTO_DEF, "&Goto Definition\tShift-F2", 
                         "Use Source Code Explorer to search a symbol def.")

        run_menu = self.menu['run'] = wx.Menu()
        run_menu.Append(ID_DEBUG, "&Run and Debug\tShift-F5",
                                 "Execute program under debugger")
        run_menu.Append(ID_EXEC, "&Execute\tShift-Ctrl-F5", 
                                 "Full speed execution (no debugger)")
        run_menu.AppendSeparator()
        run_menu.Append(ID_KILL, "&Terminate\tCtrl-T", 
                                 "Kill external process")
        run_menu.AppendSeparator()
        run_menu.Append(ID_SETARGS, "Set &Arguments\tCtrl-A", "sys.argv")
        run_menu.AppendSeparator()
        run_menu.Append(ID_ATTACH, "Attach debugge&r\tCtrl-R", 
                                   "Connect to remote debugger")

        dbg_menu = self.menu['debug'] = wx.Menu()
        dbg_menu.Append(ID_STEPIN, "&Step Into\tF8",
                        help="Execute, stepping into functions")
        dbg_menu.Append(ID_STEPNEXT, "Step &Next\tShift-F8",
                        help="Execute until the next line (step over)")
        dbg_menu.Append(ID_STEPRETURN, "Step &Return\tCtrl-Shift-F8",
                        help="Execute until the current function returns")
        dbg_menu.Append(ID_CONTINUETO, "Continue to\tCtrl-F8",
                        help="Execute until the current line is reached")
        dbg_menu.Append(ID_CONTINUE, "&Continue\tF5",
                        help="Execute unitl a breakpoint is encountered.")
        dbg_menu.Append(ID_JUMP, "&Jump to\tCtrl-F9",
                        help="Set the next line that will be executed.")
        dbg_menu.Append(ID_QUIT, "&Quit",
                        help=" The program being executed is aborted.")
        dbg_menu.Append(ID_INTERRUPT, "Interrupt\tCtrl-I",
                        help="Pause program and wait debug interaction")
        dbg_menu.AppendSeparator()
        dbg_menu.Append(ID_EVAL, "Quick &Eval\tShift-F9", 
                        help="Evaluate selected text (expression) in context")
        dbg_menu.AppendSeparator()
        dbg_menu.Append(ID_BREAKPOINT, "Toggle &Breakpoint\tF9",
                        help="Set or remove a breakpoint in the current line")
        dbg_menu.Append(ID_ALTBREAKPOINT, "Toggle Cond./Temp. Breakpoint\tAlt-F9",
                        help="Set or remove a conditional or temporary breakpoint")
        dbg_menu.Append(ID_CLEARBREAKPOINTS, "Clear All Breakpoint\tCtrl-Shift-F9")
        
        help_menu = self.menu['help'] = wx.Menu()
        help_menu.Append(wx.ID_HELP, "Quick &Help\tF1",
                        help="help() on selected expression")
        help_menu.AppendSeparator()
        help_menu.Append(wx.ID_ABOUT, "&About...")
        
        win_menu = self.menu['window'] = wx.Menu()
        self.windows = {}
        # Default window menu to select a editor tab
        self.AppendWindowMenuItem("Editor tabs...", (), self.OnWindowMenu)
        win_menu.AppendSeparator()
        for win_name, win_panes in [('Shell', ('shell', )), 
            ('Explorer', ('explorer', )),
            ('Debugging', ('environ', 'stack', 'debug', 'console', )),
            ]:
            self.AppendWindowMenuItem(win_name, win_panes, self.OnWindowMenu)

        self.menubar.Append(file_menu, "&File")
        self.menubar.Append(edit_menu, "&Edit")
        self.menubar.Append(run_menu, "&Run")
        self.menubar.Append(dbg_menu, "&Debug")
        self.menubar.Append(win_menu, "&Window")
        self.menubar.Append(help_menu, "&Help")
        
        self.SetMenuBar(self.menubar)

        self.statusbar = CustomStatusBar(self)
        self.SetStatusBar(self.statusbar)

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
        self.toolbar.AddCheckTool(ID_DESIGNER, "Designer", 
                                  images.designer.GetBitmap(), wx.NullBitmap,
                                  "Designer!")

        self.toolbar.Realize()

        menu_handlers = [
            (wx.ID_NEW, self.OnNew),
            (wx.ID_OPEN, self.OnOpen),
            (ID_OPEN_MODULE, self.OnOpenModule),
            (wx.ID_SAVE, self.OnSave),
            (wx.ID_SAVEAS, self.OnSaveAs),
            (wx.ID_CLOSE, self.OnCloseChild),
            (ID_RUN, self.OnRun),
            (ID_EXEC, self.OnExecute),
            (ID_SETARGS, self.OnSetArgs),
            (ID_KILL, self.OnKill),
            (ID_ATTACH, self.OnAttachRemoteDebugger),
            (ID_DEBUG, self.OnDebugCommand),
            (ID_EXPLORER, self.OnExplorer),
            (ID_DESIGNER, self.OnDesigner),
            #(wx.ID_PRINT, self.OnPrint),
            (wx.ID_UNDO, self.OnEditAction),
            (wx.ID_REDO, self.OnEditAction),
            (wx.ID_FIND, self.OnEditAction),
            (wx.ID_REPLACE, self.OnEditAction),
            (wx.ID_CUT, self.OnEditAction),
            (wx.ID_COPY, self.OnEditAction),
            (wx.ID_PASTE, self.OnEditAction),
            (wx.ID_HELP, self.OnHelp),
            (ID_COMMENT, self.OnEditAction),
            (ID_GOTO, self.OnEditAction),
            (ID_GOTO_DEF, self.OnGotoDefinition),
            (ID_BREAKPOINT, self.OnEditAction),
            (ID_ALTBREAKPOINT, self.OnEditAction),
            (ID_CLEARBREAKPOINTS, self.OnEditAction),
         ]
        for menu_id, handler in menu_handlers:
            self.Bind(wx.EVT_MENU, handler, id=menu_id)

        # debugging facilities:

        self.toolbardbg = aui.AuiToolBar(self, -1, 
                            style=wx.TB_FLAT | wx.TB_NODIVIDER)
        self.toolbardbg.SetToolBitmapSize(wx.Size(*tsize))

        self.toolbardbg.AddSimpleTool(ID_RUN, "Run", images.GetRunningManBitmap())
        self.toolbardbg.AddSeparator()
        self.toolbardbg.AddSimpleTool(ID_STEPIN, "Step", images.GetStepInBitmap())
        self.toolbardbg.AddSimpleTool(ID_STEPNEXT, "Next", images.GetStepReturnBitmap())
        self.toolbardbg.AddSimpleTool(ID_CONTINUE, "Continue", images.GetContinueBitmap())
        self.toolbardbg.AddSimpleTool(ID_QUIT, "Quit", images.quit.GetBitmap())
        self.toolbardbg.AddSimpleTool(ID_EVAL, "Eval", images.GetAddWatchBitmap())
        self.toolbardbg.Realize()

        for menu_id in [ID_STEPIN, ID_STEPRETURN, ID_STEPNEXT, ID_STEPRETURN,
                        ID_CONTINUE, ID_QUIT, ID_EVAL, ID_JUMP, 
                        ID_CONTINUETO, ID_INTERRUPT]:
            self.Bind(wx.EVT_MENU, self.OnDebugCommand, id=menu_id)

        wx.GetApp().SetSplashText("Creating Panes...")

        self.debugger = Debugger(self)

        self.x = 0
        self.call_stack = StackListCtrl(self)
        self._mgr.AddPane(self.call_stack, aui.AuiPaneInfo().Name("stack").
              Caption("Call Stack").Float().FloatingSize(wx.Size(400, 100)).
              FloatingPosition(self.GetStartPosition()).DestroyOnClose(False).PinButton(True).
              MinSize((100, 100)).Right().Bottom().MinimizeButton(True))

        self.environment = EnvironmentPanel(self)
        self._mgr.AddPane(self.environment, aui.AuiPaneInfo().Name("environ").
              Caption("Environment").Float().FloatingSize(wx.Size(400, 100)).
              FloatingPosition(self.GetStartPosition()).DestroyOnClose(False).PinButton(True).
              MinSize((100, 100)).Right().Bottom().MinimizeButton(True))


        self._mgr.AddPane(self.toolbar, aui.AuiPaneInfo().Name("toolbar").
                          ToolbarPane().Top().Position(0))

        self._mgr.AddPane(self.toolbardbg, aui.AuiPaneInfo().Name("debug").
                          ToolbarPane().Top().Position(1))
                      
        self.browser = self.CreateBrowserCtrl()
        if self.browser:
            self._mgr.AddPane(self.browser, aui.AuiPaneInfo().Name("browser").
                          Caption("Simple Browser").Right().CloseButton(True))

        self.shell = Shell(self, debugger=self.debugger)
        self._mgr.AddPane(self.shell, aui.AuiPaneInfo().Name("shell").
                          Caption("Shell").
                          Bottom().Layer(1).Position(1).CloseButton(True))

        self.console = ConsoleCtrl(self)
        self._mgr.AddPane(self.console, aui.AuiPaneInfo().Name("console").
                          Caption("Console (stdio)").
                          Bottom().Layer(1).Position(2).CloseButton(True))

        self.explorer = ExplorerPanel(self)
        self._mgr.AddPane(self.explorer, aui.AuiPaneInfo().Name("explorer").
              Caption("Source Explorer").Float().FloatingSize(wx.Size(400, 100)).
              FloatingPosition(self.GetStartPosition()).DestroyOnClose(False).PinButton(True).
              MinSize((100, 100)).Left().Top().MinimizeButton(True))

        # "commit" all changes made to FrameManager   
        self._mgr.Update()

        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_CLOSE, self.OnCloseAll)

        self.Bind(wx.EVT_MENU, self.OnExit, id=wx.ID_EXIT)
        self.Bind(wx.EVT_MENU, self.OnAbout, id=wx.ID_ABOUT)

        # Connect to debugging and explorer events
        self.Connect(-1, -1, EVT_DEBUG_ID, self.GotoFileLine)
        self.Connect(-1, -1, EVT_EXCEPTION_ID, self.OnException)
        self.Connect(-1, -1, EVT_EXPLORE_ID, self.OnExplore)

        # key bindings (shortcuts). TODO: configuration
        # NOTE: wx.WXK_PAUSE doesn't work (at least in wxGTK -Ubuntu-)
        accels = [
                    (wx.ACCEL_CTRL, wx.WXK_PAUSE, ID_INTERRUPT, 
                        self.OnDebugCommand),
                    (wx.ACCEL_NORMAL, wx.WXK_PAUSE, ID_INTERRUPT, 
                        self.OnDebugCommand),
                ]
        atable = wx.AcceleratorTable([acc[0:3] for acc in accels])
        for acc in accels:
            self.Bind(wx.EVT_MENU, acc[3], id=acc[2])
        self.SetAcceleratorTable(atable)

        # bind find / replace dialog events:
        self.Bind(wx.EVT_FIND, self.OnEditAction)
        self.Bind(wx.EVT_FIND_NEXT, self.OnEditAction)
        self.Bind(wx.EVT_FIND_REPLACE, self.OnEditAction)
        self.Bind(wx.EVT_FIND_REPLACE_ALL, self.OnEditAction)
        self.Bind(wx.EVT_FIND_CLOSE, self.OnEditAction)

        
        # Initialize secondary mixins
        
        wx.GetApp().SetSplashText("Initializing Mixins...")

        TaskMixin.__init__(self)        
        PSPMixin.__init__(self)
        RepoMixin.__init__(self)
        Gui2pyMixin.__init__(self)

        # web2py initialization (on own thread to enable debugger)
        Web2pyMixin.__init__(self)

        # Restore configuration

        wx.GetApp().SetSplashText("Restoring previous Layout...")
        
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

        wx.GetApp().SetSplashText("Opening previous files...")
        
        # restore previuous open files
        wx.CallAfter(self.DoOpenFiles)

        # set not executing (hide debug panes)
        self.executing = False
        
                
    def GetStartPosition(self):

        self.x = self.x + 20
        x = self.x
        pt = self.ClientToScreen(wx.Point(0, 0))
        
        return wx.Point(pt.x + x, pt.y + x)

    @property
    def active_child(self):
        return self.GetActiveChild()

    def get_executing(self):
        return self._executing

    def set_executing(self, value=False):
        self._executing = value
        self._mgr.GetPane("environ").Show(self._executing)
        self._mgr.GetPane("stack").Show(self._executing)
        self._mgr.Update()
    
    executing = property(get_executing, set_executing)

    def AppendWindowMenuItem(self, win_name, win_panes, evt_handler):
        menu_id = wx.NewId()
        win_menu = self.menu['window']
        win_menu.Append(menu_id, win_name, )
        self.windows[menu_id] = win_panes
        self.Bind(wx.EVT_MENU, evt_handler, id=menu_id)

    def OnWindowMenu(self, event):
        menu_id = event.GetId()
        panes = self.windows[menu_id]
        if panes:
            # show al panes related to the menu item
            for pane in panes:
                self._mgr.GetPane(pane).Show()
            self._mgr.Update()
        else:
            # show a children window list
            dlg = wx.SingleChoiceDialog(
                self, 'Select the tab to activate', 'Windows',
                sorted([child.GetFilename() for child in self.children]),
                wx.CHOICEDLG_STYLE
                )
            if dlg.ShowModal() == wx.ID_OK:
                self.DoOpen(dlg.GetStringSelection())
            dlg.Destroy()
            
    def Cleanup(self, event):
        if 'repo' in ADDONS:
            self.RepoMixinCleanup()
        # A little extra cleanup is required for the FileHistory control
        if hasattr(self, "filehistory"):
            # save recent file history in config file
            for filenum in range(0, self.filehistory.Count):
                filename = self.filehistory.GetHistoryFile(filenum)
                wx.GetApp().config.set('HISTORY', 'file_%s' % filenum, filename)
            del self.filehistory
            #self.recent_files_submenu.Destroy() # warning: SEGV!

    def OnCloseChild(self, event):
        "Close a child window"
        if self.active_child:
            self.active_child.Close()     

    def OnCloseAll(self, event):
        "Perform a ordered destruction, clean-up and update database / config"
        
        # detach the current active task (if any)
        if self.task_id:
            self.deactivate_task()
        
        # get global config instance
        config = wx.GetApp().config
        
        # Close all child windows (remember opened):
        open_files = []
        while self.active_child:
            open_files.append(self.active_child.GetFilename())
            if not self.active_child.Close():
                event.Veto()
                return 
        # clean old config file values and store new filenames:
        if config.has_section('FILES'):
            config.remove_section('FILES')
        config.add_section('FILES')
        for i, filename in enumerate(open_files):
            config.set('FILES', "file_%02d" % i, filename)
        
        # Save current perspective layout. WARNING: all panes must have a name! 
        if hasattr(self, "_mgr"):
            perspective = self._mgr.SavePerspective()
            config.set('AUI', 'perspective', perspective)
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
            wildcard="Python Files (*.py)|*.py|Python Windows Files (*.pyw)|*.pyw",
            style=wx.OPEN 
            )
        # set the path to current active editing file
        if self.active_child and self.active_child.GetFilename():
            dlg.SetDirectory(os.path.dirname(self.active_child.GetFilename()))
        if dlg.ShowModal() == wx.ID_OK:
            # This returns a Python list of files that were selected.
            filename = dlg.GetPaths()[0]        
            self.DoOpen(filename)
            # add it to the history (if it is available)
            if hasattr(self, "filehistory"):
                self.filehistory.AddFileToHistory(filename)

        dlg.Destroy()

    def OnOpenModule(self, event=None):
        name = arg = self.active_child.GetSelectedText().strip()
        dlg = wx.TextEntryDialog(self,
             "Enter the name of a Python module\n"
             "to search on sys.path and open:",            
             'Open Module', name)
        if dlg.ShowModal() == wx.ID_OK:
            name = dlg.GetValue()
        dlg.Destroy()
        if name:
            name = name.strip()
        if not name:
            return
        cwd = os.getcwd()
        try:
            # set the path to current active editing file
            if self.active_child and self.active_child.GetFilename():
                os.chdir(os.path.dirname(self.active_child.GetFilename()))
            (f, file, (suffix, mode, type)) = imp.find_module(name)
            if type != imp.PY_SOURCE:
                raise RuntimeError("Unsupported type: "
                    "%s is not a source module" % name)
            if f:
                f.close()
            self.DoOpen(file)
        except (NameError, ImportError, RuntimeError), msg:
            dlg = wx.MessageDialog(self, unicode(msg), "Import error",
                       wx.OK | wx.ICON_EXCLAMATION)
            dlg.ShowModal()
            dlg.Destroy()
        finally:
            os.chdir(cwd)
            
    def OnFileHistory(self, evt):
        # get the file based on the menu ID
        filenum = evt.GetId() - wx.ID_FILE1
        filepath = self.filehistory.GetHistoryFile(filenum)
        self.DoOpen(filepath)
        # add it back to the history so it will be moved up the list
        self.filehistory.AddFileToHistory(filepath)

    def DoOpen(self, filename, title=""):
        if not (self.debugger and self.debugger.is_remote()):
            # normalize filename for local files! (mostly fix path separator)
            filename = os.path.abspath(filename)
        found = [child for child in self.children if child.GetFilename()==filename]
        if not found:
            child = AUIChildFrame(self, filename, title)
            child.Show()
            self.children.append(child)
            if self.task_id:
                self.load_task_context(filename, child)
            if self.explorer:
                wx.CallAfter(self.explorer.ParseFile, filename)
        else:
            child = found[0]
            # do not interfere with shell focus
            if not self.shell.HasFocus():
                child.Activate()
                child.SetFocus()
        return child

    def DoOpenFiles(self):
        "Open previous session files"
        
        # read configuration file 
        config = wx.GetApp().config
        if config.has_section('FILES'):
            open_files = config.items("FILES") 
            open_files.sort()
            # open previous session files
            for option_name, filename in open_files:
                if os.path.exists(filename):
                    self.DoOpen(filename)
            # activate last current file (first in the list):
            if open_files:
                self.DoOpen(open_files[0][1])

    def OnSave(self, event):
        if self.active_child:
            self.active_child.OnSave(event)

    def OnSaveAs(self, event):
        if self.active_child:
            self.active_child.OnSaveAs(event)

    def DoClose(self, child, filename):
        self.children.remove(child)
        if self.task_id or True:
            self.save_task_context(filename, child)
        if self.explorer:
            wx.CallAfter(self.explorer.RemoveFile, filename)

    def OnExplorer(self, event):
        if self.active_child:
            self.explorer.ParseFile(self.active_child.GetFilename())
            self._mgr.GetPane("explorer").Show(True)
            self._mgr.Update()
            self.explorer.SetFocus()

    def OnSetArgs(self, event):
        dlg = wx.TextEntryDialog(self, 'Enter program arguments (sys.argv):', 
            'Set Arguments', self.lastprogargs)
        if dlg.ShowModal() == wx.ID_OK:
            self.lastprogargs = dlg.GetValue()
        dlg.Destroy()
    
    def OnRun(self, event):
        self.OnExecute(event, debug=False)
        
    def OnExecute(self, event, debug=True):
        if self.active_child and not self.console.process:
            filename = self.active_child.GetFilename()
            cdir, filen = os.path.split(filename)
            if not cdir: 
                cdir = "."
            cwd = os.getcwd()
            try:
                os.chdir(cdir)
                largs = self.lastprogargs and ' ' + self.lastprogargs or ""
                if wx.Platform == '__WXMSW__':
                    pythexec = sys.prefix.replace("\\", "/") + "/pythonw.exe"
                    filename = filename.replace("\\", "/")
                else:
                    pythexec = sys.executable
                self.Execute((pythexec + " -u " + (debug and self.pythonargs or '') + ' "' + 
                    filename + '"'  + largs), filen)
                self.statusbar.SetStatusText("Executing: %s" % (filename), 1)
                if debug:
                    self.debugger.attach()

            except Exception, e:
                raise
                #ShowMessage("Error Setting current directory for Execute")
            finally:
                os.chdir(cwd)
    
    def OnKill(self, event):
        if self.console.process:
            self.console.process.Kill(self.console.process.pid, wx.SIGKILL)
            self.statusbar.SetStatusText("killed", 1)
        else:
            self.statusbar.SetStatusText("", 1)
        self.executing = False


    def Execute(self, command, filename, redin="", redout="", rederr=""):
        "Execute a command and redirect input/output/error to internal console"
        statusbar = self.statusbar
        console = self.console
        statusbar.SetStatusText("Executing %s" % command, 1)
        parent = self
        
        class MyProcess(wx.Process):
            "Custom Process Class to handle OnTerminate event method"

            def OnTerminate(self, pid, status):
                "Clean up on termination (prevent SEGV!)"
                console.process = None
                parent.executing = False
                statusbar.SetStatusText("Terminated: %s!" % filename, 0)
                statusbar.SetStatusText("", 1)
        
        process = console.process = MyProcess(self)
        self.executing = True
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

    def OnExplore(self, event=None):
        if event:
            filename, lineno = event.data
            child = self.DoOpen(filename)
            if child:
                child.GotoLineOffset(lineno, 1)

    def GotoFileLine(self, event=None, running=True):
        if event and running:
            filename, lineno, context, orig_line = event.data
            if context:
                call_stack = context['call_stack']
                environment = context['environment']
            else:
                call_stack = environment = {}
            self.call_stack.BuildList(call_stack)
            self.environment.BuildTree(environment,
                                       sort_order=('locals', 'globals'))
        elif not running:
            filename, lineno, offset = event
        # first, clean all current debugging markers
        for child in self.children:
            if running:
                child.SynchCurrentLine(None)
                self.debugging_child = None
        # then look for the file being debugged
        if event and filename:
            child = self.DoOpen(filename)
            if child:
                if running:
                    child.SynchCurrentLine(lineno)
                    self.debugging_child = child
                else:
                    child.GotoLineOffset(lineno, offset)

    def GetBreakpoints(self):
        if self.temp_breakpoint:
            yield self.temp_breakpoint
            self.temp_breakpoint = None
        for child in self.children:
            yield child.GetFilename(), child.GetBreakpoints()
        
    def GetLineText(self, filename, lineno):
        "Returns source code"
        # used by the debugger to detect modifications runtime
        child = self.DoOpen(filename)
        if child:
            return child.GetLineText(lineno)

    def Readline(self):
        # ensure "console" pane is visible
        self._mgr.GetPane("console").Show()
        self._mgr.Update()
        # read user input and return it
        return self.console.readline()

    def Write(self, text):
        self.console.write(text)
                    
    def OnDebugCommand(self, event):
        event_id = event.GetId()

        # start debugger (if not running):
        if not self.executing:
            print "*** Execute!!!!"
            # should it open debugger inmediatelly or continue?
            cont = event_id in (ID_DEBUG, ID_CONTINUE, ID_CONTINUETO)
            self.debugger.init(cont)
            if event_id == ID_CONTINUETO and self.active_child:
                # set temp breakpoint to be hit on first run!
                lineno = self.active_child.GetCurrentLine()
                filename = self.active_child.GetFilename()
                self.temp_breakpoint = (filename, {lineno: (1, None)})
            self.OnExecute(event)
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
        elif event_id == ID_QUIT:
            self.debugger.Quit()
        elif event_id == ID_INTERRUPT:
            self.debugger.Interrupt()
        elif event_id == ID_EVAL and self.active_child:
            # Eval selected text (expression) in debugger running context
            arg = self.active_child.GetSelectedText()
            val = self.debugger.Eval(arg)
            dlg = wx.MessageDialog(self, "Expression: %s\nValue: %s" % (arg, val), 
                                   "Debugger Quick Eval",
                                   wx.ICON_INFORMATION | wx.OK )
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
            self.debugger.Continue(filename=filename, lineno=lineno)

    def OnHelp(self, event):
        "Show help on selected text"
        # TODO: show html help!
        sel = self.active_child.GetSelectedText()
        stdin, stdout, sterr = sys.stdin, sys.stdout, sys.stderr 
        try:
            sys.stdin = sys.stdout = sys.stderr = self.console
            help(sel.encode("utf8"))
        except Exception, e:
            tip = unicode(e)
        finally:
            sys.stdin, sys.stdout, sys.stderr = stdin, stdout, sterr 

        
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

    def OnGotoDefinition(self, event):
        if self.active_child and self.explorer:
            filename = self.active_child.GetFilename()
            filename, lineno, offset = self.active_child.GetDefinition()
            if filename:
                child = self.DoOpen(filename)
                if child:
                    child.GotoLineOffset(lineno, offset)

    def ExceptHook(self, extype, exvalue, trace): 
        exc = traceback.format_exception(extype, exvalue, trace) 
        #for e in exc: wx.LogError(e) 
        # format exception message
        title = traceback.format_exception_only(extype, exvalue)[0]
        if not isinstance(title, unicode):
            title = title.decode("latin1", "ignore")
        msg = ''.join(traceback.format_exception(extype, exvalue, trace))
        # display the exception
        print u'Unhandled Error: %s' % title
        print >> sys.stderr, msg
        # ignore internal wx assertion (on some wx builds)
        PyAssertion = getattr(wx, "PyAssertion", None)
        if PyAssertion and extype != wx.PyAssertion and not DEBUG:
            dlg = wx.lib.dialogs.ScrolledMessageDialog(self, msg, title)
            dlg.ShowModal()
            dlg.Destroy()

    def OnException(self, event):
        # unpack remote exception contents
        title, extype, exvalue, trace, msg = event.data
        if not isinstance(title, unicode):
            title = title.decode("latin1", "ignore")
        # display the exception
        print u'Unhandled Remote Error: %s' % title
        dlg = wx.lib.dialogs.ScrolledMessageDialog(self, msg, title)
        dlg.ShowModal()
        dlg.Destroy()
        # automatic defect classification
        if extype:
            # stack trace (tb) should be processed:
            if trace:
                filename, lineno, function_name, text = trace[-1]
                # Automatic Error Classification (PSP Defect Type Standard):
                defect_type_standard = {
                    '20': ('SyntaxError', ), # this should be cached by the editor
                    '40': ('NameError', 'LookupError', 'ImportError'),
                    '50': ('TypeError', 'AttributeError'),
                    '60': ('AssertionError', ), #TODO: unittest/doctests
                    '70': ('ValueError', 'ArithmeticError', 'EOFError', 'BufferError'),
                    '80': ('RuntimeError', ),
                    '90': ('SystemError', 'MemoryError', 'ReferenceError', ),
                    '100': ('EnvironmentError', ), # TODO: libraries?
                    }
                # Find the related defect_type code for the exception value:
                for k, v in defect_type_standard.items():
                    if extype == v:
                        defect_type = k
                        break
                else:
                    defect_type = '80'  # default unclassified defect type
                self.NotifyDefect(summary=title, type=defect_type, 
                                  filename=filename, 
                                  description="", lineno=lineno, offset=1)
            else:
                print "Not notified!"

    def OnAttachRemoteDebugger(self, event):
        dlg = wx.TextEntryDialog(self, 
                'Enter the address of the remote qdb frontend:', 
                'Attach to remote debugger', 
                'host="localhost", port=6000, authkey="secret password"')
        if dlg.ShowModal() == wx.ID_OK:
            # detach any running debugger
            self.debugger.detach()
            # step on connection:
            self.debugger.start_continue = False
            # get and parse the URL (TODO: better configuration)
            d = eval("dict(%s)" % dlg.GetValue(), {}, {})
            # attach local thread (wait for connections)
            self.debugger.attach(d['host'], d['port'], d['authkey'])
            # set flag to not start new processes on debug command
            self.executing = True
        dlg.Destroy()

    def NotifyRepo(self, filename, action="", status=""):
        if 'repo' in ADDONS:
            wx.PostEvent(self, RepoEvent(filename, action, status))
        # notify the explorer to refresh the module symbols
        if self.explorer:
            self.explorer.ParseFile(filename, refresh=True)

    def ShowInfoBar(self, message, flags=wx.ICON_INFORMATION, key=None, 
                    auto_dismiss=False):
        "Show message in a information bar (between menu and toolbar)"
        if not infobar:
            return
        if key not in self.infobars:
            # create a new InfoBar if not exists
            self.infobars[key] = infobar.InfoBar(self)
            # "veto" resize event (spurious AUI OnSize event workaround)
            self.infobars[key].Bind(wx.EVT_SIZE, lambda e: None)
            # create the AUI Pane 
            # (do not set name to override be hidden by LoadPerspective)
            self._mgr.AddPane(self.infobars[key], aui.AuiPaneInfo().
                                          Top().Layer(100 - len(self.infobars)).
                                          BestSize((300, 30)).
                                          CaptionVisible(False).
                                          CloseButton(False).
                                          MaximizeButton(False).
                                          MinimizeButton(False))
        # workaround: show infobar to layout it correctly
        self.infobars[key].DoShow()
        # show message when this event finish
        wx.CallAfter(self.infobars[key].ShowMessage, message, flags)
        # workaround: size event to correctly wrap text if window is resized
        evt = wx.SizeEvent(self.infobars[key].GetClientSize())
        wx.CallAfter(self.infobars[key]._text.OnSize, evt)
        if auto_dismiss:
            wx.CallLater(5000, self.infobars[key].Dismiss)
    

class CustomStatusBar(wx.StatusBar):
    def __init__(self, parent):
        self.parent = parent
        wx.StatusBar.__init__(self, parent, -1)
        self.SetFieldsCount(7)
        # Sets the three fields to be relative widths to each other.
        self.SetStatusWidths([-2, -2, -5, 100, 85, 65, -2])
        self.SetStatusText("Ready", 0)
        self.SetStatusText("Welcome To ide2py!", 1)
        self.SetStatusText(__copyright__, 6)
        self.eol_choice = wx.Choice(self, wx.ID_ANY,
                                             choices = ["win", "mac", "unix",])
        self.eol_choice.SetToolTip(wx.ToolTip("End-Of-Line conversion"))
        self.blank_check = wx.CheckBox(self, 1001, "blanks")
        self.blank_check.SetToolTip(wx.ToolTip("Show/Hide blanks: CR, LF, TAB"))
        self.Bind(wx.EVT_CHECKBOX, self.OnToggleBlanks, self.blank_check)
        # set the initial position of the choice
        self.Reposition()
        self.Bind(wx.EVT_CHOICE, self.OnToggleEOL, self.eol_choice)
        ##self.Bind(wx.EVT_SIZE, self.OnSize)
        ##self.Bind(wx.EVT_IDLE, self.OnIdle)
        self.size_changed = False
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_IDLE, self.OnIdle)
    
    def OnToggleEOL(self, event):
        self.parent.active_child.ChangeEOL(self.eol_choice.GetSelection())

    def OnToggleBlanks(self, event):
        self.parent.active_child.ToggleBlanks(self.blank_check.GetValue())

    def OnSize(self, evt):
        self.Reposition()  # for normal size events
        # Set a flag so the idle time handler will also do the repositioning.
        # It is done this way to get around a buglet where GetFieldRect is not
        # accurate during the EVT_SIZE resulting from a frame maximize.
        self.size_changed = True

    def OnIdle(self, evt):
        if self.size_changed:
            self.Reposition()

    # reposition the checkbox
    def Reposition(self):
        rect = self.GetFieldRect(3)
        self.eol_choice.SetPosition((rect.x, rect.y))
        self.eol_choice.SetSize((rect.width, rect.height))
        rect = self.GetFieldRect(4)
        self.blank_check.SetPosition((rect.x + 2, rect.y + 2))
        self.blank_check.SetSize((rect.width - 4, rect.height - 4))
        self.size_changed = False



class AUIChildFrame(aui.AuiMDIChildFrame):

    def __init__(self, parent, filename, title=""):
        self.filename = filename
        self.parent = parent
        aui.AuiMDIChildFrame.__init__(self, parent, -1,
                                         title="")  
        app = wx.GetApp()
        
        self.editor = EditorCtrl(self,-1, filename=filename,    
                                 debugger=parent.debugger,
                                 lang="python", 
                                 title=title,
                                 cfg=app.get_config("EDITOR"),
                                 cfg_styles=app.get_config("STC.PY"))
        sizer = wx.BoxSizer()
        sizer.Add(self.editor, 1, wx.EXPAND)
        self.SetSizer(sizer)        
        wx.CallAfter(self.Layout)

    def OnCloseWindow(self, event):
        ctrl = event.GetEventObject()  
        result = self.editor.OnClose(event)
        if result is not None:
            self.parent.DoClose(self, self.GetFilename())
            self.editor.Destroy()  # fix to re-paint correctly
            aui.AuiMDIChildFrame.OnCloseWindow(self, event)

    def OnSave(self, event):
        self.editor.OnSave(event)

    def OnSaveAs(self, event):
        self.editor.OnSaveAs(event)

    def OnEditAction(self, event):
        "Dispatch a top level event to the active child editor"
        if isinstance(event, wx.FindDialogEvent):
            # Find / Replace related dialog events (received by the main frame)
            handlers = {
                wx.EVT_FIND.typeId: self.editor.OnFindReplace,
                wx.EVT_FIND_NEXT.typeId: self.editor.OnFindReplace,
                wx.EVT_FIND_REPLACE.typeId: self.editor.OnFindReplace,
                wx.EVT_FIND_REPLACE_ALL.typeId: self.editor.OnReplaceAll,
                wx.EVT_FIND_CLOSE.typeId: self.editor.OnFindClose,
            }
            handlers[event.GetEventType()](event)
        else:
            # Menu events (received by the main frame)
            handlers = {
                wx.ID_UNDO: self.editor.DoBuiltIn,
                wx.ID_REDO: self.editor.DoBuiltIn,
                wx.ID_FIND: self.editor.DoFind,
                wx.ID_REPLACE: self.editor.DoReplace,
                wx.ID_COPY: self.editor.DoBuiltIn,
                wx.ID_PASTE: self.editor.DoBuiltIn,
                wx.ID_CUT: self.editor.DoBuiltIn,
                ID_BREAKPOINT: self.editor.ToggleBreakpoint,
                ID_ALTBREAKPOINT: self.editor.ToggleAltBreakpoint,
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
    
    def GetLineText(self, lineno):
        return self.editor.GetLineText(lineno)

    def GetWord(self):
        return self.editor.GetWord(whole=True)

    def GetDefinition(self):
        return self.editor.GetDefinition()
        
    def SynchCurrentLine(self, lineno):
        if lineno:
            pass##self.SetFocus()
        return self.editor.SynchCurrentLine(lineno)

    def GotoLineOffset(self, lineno, offset):
        if lineno:
            self.SetFocus()
            self.editor.GotoLineOffset(lineno, offset)

    def HighlightLines(self, line_numbers, style=0):
        self.editor.HighlightLines(line_numbers)

    def NotifyDefect(self, *args, **kwargs):
        self.parent.NotifyDefect(*args, **kwargs)
    
    def NotifyRepo(self, *args, **kwargs):
        self.parent.NotifyRepo(*args, **kwargs)

    def GetBreakpoints(self):
        return self.editor.GetBreakpoints()

    def ToggleBreakpoint(self, **kwargs):
        return self.editor.ToggleBreakpoint(evt=None, **kwargs)

    def SetFold(self, **kwargs):
        self.editor.SetFold(**kwargs)

    def FoldAll(self, expanding=False):
        return self.editor.FoldAll(expanding)
                
    def GetFoldAll(self):
        return self.editor.GetFoldAll()

    def UpdateStatusBar(self, statustext, eolmode, encoding):
        self.parent.statusbar.SetStatusText(statustext, 1)
        self.parent.statusbar.SetStatusText(self.filename, 2)
        self.parent.statusbar.eol_choice.SetSelection(eolmode)
        self.parent.statusbar.SetStatusText(encoding, 5)

    def ShowInfoBar(self, message, flags=wx.ICON_INFORMATION, key=None, parent=None):
        # TODO: add the infobar to the notebook
        if infobar:
            self.parent.ShowInfoBar(message, flags=flags, key="editor", 
                                auto_dismiss=True)
        
    def ChangeEOL(self, eol):
        self.editor.ChangeEOL(eol)
    
    def ToggleBlanks(self, visible):
        self.editor.ToggleBlanks(visible)


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
        if advancedsplash and os.path.exists(SPLASH_IMAGE):
            bitmap = wx.Image(SPLASH_IMAGE, wx.BITMAP_TYPE_ANY).ConvertToBitmap()
            self.splash_frame = advancedsplash.AdvancedSplash(
                None, bitmap=bitmap, timeout=2000,
                agwStyle=advancedsplash.AS_TIMEOUT | 
                         advancedsplash.AS_CENTER_ON_SCREEN |
                         advancedsplash.AS_SHADOW_BITMAP,
                         shadowcolour=wx.ColourDatabase().Find("yellow"),
                )
            import wx.lib.agw.speedmeter as SM
            pi=3.14
            self.SpeedWindow1 = SM.SpeedMeter(self.splash_frame,
                                          agwStyle=SM.SM_DRAW_HAND |
                                          SM.SM_DRAW_SECTORS |
                                          SM.SM_DRAW_MIDDLE_TEXT |
                                          SM.SM_DRAW_SECONDARY_TICKS
                                          )
            self.SpeedWindow1.SetAngleRange(-pi/6, 7*pi/6)
            intervals = range(0, 201, 20)
            self.SpeedWindow1.SetIntervals(intervals)
            colours = [wx.BLACK]*10
            self.SpeedWindow1.SetIntervalColours(colours)
            ticks = [str(interval) for interval in intervals]
            self.SpeedWindow1.SetTicks(ticks)
            self.SpeedWindow1.SetTicksColour(wx.WHITE)
            self.SpeedWindow1.SetNumberOfSecondaryTicks(5)
            self.SpeedWindow1.SetTicksFont(wx.Font(7, wx.SWISS, wx.NORMAL, wx.NORMAL))
            self.SpeedWindow1.SetMiddleText("Km/h")
            # Assign The Colour To The Center Text
            self.SpeedWindow1.SetMiddleTextColour(wx.WHITE)
            # Assign A Font To The Center Text
            self.SpeedWindow1.SetMiddleTextFont(wx.Font(8, wx.SWISS, wx.NORMAL, wx.BOLD))

            # Set The Colour For The Hand Indicator
            self.SpeedWindow1.SetHandColour(wx.Colour(255, 50, 0))

            # Do Not Draw The External (Container) Arc. Drawing The External Arc May
            # Sometimes Create Uglier Controls. Try To Comment This Line And See It
            # For Yourself!
            self.SpeedWindow1.DrawExternalArc(False)        

            # Set The Current Value For The SpeedMeter
            self.SpeedWindow1.SetSpeedValue(44)
            if RAD2PY_ICON:
                ib = wx.IconBundle()
                ib.AddIconFromFile(RAD2PY_ICON, wx.BITMAP_TYPE_ANY)
                self.splash_frame.SetIcons(ib)
                ##self.splash_frame.SetIcon(wx.Icon(RAD2PY_ICON, 
                ##                                  wx.BITMAP_TYPE_ICO))
            self.splash_frame.SetTextColour(wx.WHITE)
            font = wx.Font(
                    pointSize = 9, family = wx.DEFAULT, 
                    style = wx.NORMAL, weight = wx.BOLD
                    )
            self.splash_frame.SetFont(font)
            self.splash_frame.SetTextFont(font)
            self.SetSplashText("Loading...")
            # Draw splash screen first, then proceed with initialization
            wx.CallAfter(self.InitApp)
        else:
            self.splash_frame = None
            self.InitApp()
        return True
    
    def SetSplashText(self, text):
        "Draw centered text at Splash Screen"
        if self.splash_frame:
            w, h = self.splash_frame.GetTextExtent(text)
            self.splash_frame.SetTextPosition((105 - w/2, 102))
            self.splash_frame.SetText(text)
            
    def InitApp(self):
        self.config = ConfigParser.ConfigParser()
        # read default configuration
        self.config.read("ide2py.ini.dist")
        # merge user custom configuration
        self.config.read(CONFIG_FILE)
        if not self.config.sections():
            raise RuntimeError("No configuration found, use ide2py.ini.dist!")
        # initialize the internal database
        db_conf = self.get_config("DATABASE")
        self.db = Database(**dict(db_conf.items()))        
        # create the IDE main window
        self.main_frame = PyAUIFrame(None)
        self.main_frame.Show()

    def OnExit(self):
        self.write_config()

    def get_config(self, section):
        return FancyConfigDict(section, self.config)

    def write_config(self):
        self.config.write(open(CONFIG_FILE, "w"))

    def get_db(self):
        return self.db


# search actual installation directory
if not hasattr(sys, "frozen"): 
    basepath = __file__
else:
    basepath = sys.executable
INSTALL_DIR = os.path.dirname(os.path.abspath(basepath))

if sys.platform == 'win32' and hasattr(sys, "frozen"):
    # On windows, load it from the executable (only if compiled to exe)
    RAD2PY_ICON = sys.executable
elif not os.path.exists(RAD2PY_ICON):
    # do not display the icon if not accessible
    RAD2PY_ICON = None


if __name__ == '__main__':
    #  get rid of ubuntu unity and force use of the old scroll bars
    os.environ['LIBOVERLAY_SCROLLBAR'] = '0'
    #  disable ubuntu menubar too
    os.environ['UBUNTU_MENUPROXY'] = '0'
    # start main app, avoid wx redirection on windows
    app = MainApp(redirect=False)
    app.MainLoop()



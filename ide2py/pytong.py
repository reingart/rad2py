#!/usr/bin/env python
# -*- coding: utf-8 -*-

import threading, time, os, sys, imp, unittest
from optparse import OptionParser

try:
    import wx, wx.lib.newevent
except ImportError:
    import tkMessageBox
    tkMessageBox.showerror("wxPython not found",
            "This program requires the wxPython module to be installed " + 
            "for the current Python version.\nSee http://www.wxpython.org")
    sys.exit(1)

VERSION = "0.1"
ID_LOAD  = wx.NewId()
ID_ABOUT = wx.NewId()
ID_START = wx.NewId()
ID_STOP  = wx.NewId()
ID_CLEAR  = wx.NewId()
ID_TB = wx.NewId() # Toolbar on/off

RunDepth = 0
ShouldStop = False

options = None # Command line options
filename = "" # startup file

import images
ICON_OK = images.circle_green.GetBitmap()
ICON_NOK = images.circle_red.GetBitmap()
ICON_DEFAULT = images.circle_gray.GetBitmap()

TestResultEvent, EVT_TESTRESULT = wx.lib.newevent.NewEvent()
StopEvent,       EVT_STOP       = wx.lib.newevent.NewEvent()
ItemTextEvent,   EVT_ITEMTEXT   = wx.lib.newevent.NewEvent()
AppendConsoleEvent, EVT_CONSOLE = wx.lib.newevent.NewEvent()

def RunTest(frame, item):
    """Recursively run tests from tree item."""
    global RunDepth

    if ShouldStop:
        print "Returning because of ShouldStop"
        wx.PostEvent(frame, TestResultEvent(item=item, image=frame.IM_DEFAULT))

        if RunDepth == 0:
            wx.PostEvent(frame, StopEvent())
        return False

    RunDepth += 1
    if frame.tree.GetChildrenCount(item) > 0:
        wx.PostEvent(frame, TestResultEvent(item=item, image=frame.IM_DEFAULT))
        i, cookie = frame.tree.GetFirstChild(item)
        success = True
        while i.IsOk():
            success &= RunTest(frame, i)
            i, cookie = frame.tree.GetNextChild(item, cookie)
    else: # Single test case (stop condition)
        data = frame.tree.GetPyData(item)
        result = unittest.TestResult()
        wx.PostEvent(frame, ItemTextEvent(item=item, running = True))
        data.run(result)
        wx.PostEvent(frame, ItemTextEvent(item=item, running = False))
        success = result.wasSuccessful()
        frame.results.append(result)
        if not success:
            for error in result.errors:
                wx.PostEvent(frame, AppendConsoleEvent(text="ERROR IN " + error[0].__str__() + '\n'))
                wx.PostEvent(frame, AppendConsoleEvent(text=error[1]))
            for error in result.failures:
                wx.PostEvent(frame, AppendConsoleEvent(text="FAILURE IN " + error[0].__str__() + '\n'))
                wx.PostEvent(frame, AppendConsoleEvent(text=error[1]))
    # update icon
    if (success):
        wx.PostEvent(frame, TestResultEvent(item=item, image=frame.IM_OK))
    else:
        wx.PostEvent(frame, TestResultEvent(item=item, image=frame.IM_NOK))
    RunDepth -= 1
    if RunDepth == 0:
        wx.PostEvent(frame, StopEvent())
    return success

class Frame(wx.Frame):
    """Main frame."""
    def __init__(self, title):
        wx.Frame.__init__(self, None, wx.ID_ANY, title, size=(480, 480))
        self.CreateStatusBar(1, 0, 0, "")
    
        self.running = None
        self.results = []
        ##self.SetIcon(wx.Icon("icons/icon32x16b.xpm", wx.BITMAP_TYPE_XPM))

        menu = wx.Menu()
        menu.Append(ID_LOAD, "&Load...\tCtrl+L")
        menubar = wx.MenuBar()
        menubar.Append(menu, "&Commands")
        
        self.menuTests = wx.Menu()
        self.menuTests.Append(ID_START, "Run\tF5")
        self.menuTests.Append(ID_STOP, "Stop")
        self.menuTests.Append(ID_CLEAR, "Clear")
        menubar.Append(self.menuTests, "&Tests")

        menuView = wx.Menu()
        menuView.AppendCheckItem(ID_TB, "Toolbar")
        menuView.Check(ID_TB, True)
        menubar.Append(menuView, "&View")
        
        menuHelp = wx.Menu()
        menuHelp.Append(wx.ID_HELP, "Manual\tF1")
        menuHelp.Append(ID_ABOUT, "&About...")
        menubar.Append(menuHelp, "&Help")
        self.SetMenuBar(menubar)
        
        tb = wx.ToolBar(self, -1, style=wx.TB_FLAT)
        tb.SetToolBitmapSize((22, 22))
        tb.AddTool(ID_START, ICON_OK)
        tb.AddTool(ID_STOP, ICON_NOK)
        tb.AddTool(ID_CLEAR, ICON_DEFAULT)
        self.tb = tb
        tb.Realize()

        self.SetMode(False)

        splitter = wx.SplitterWindow(self, -1, style=0)

        self.tree = wx.TreeCtrl(splitter, style = wx.TR_HAS_BUTTONS | wx.TR_LINES_AT_ROOT)
        self.textCtrl = wx.TextCtrl(splitter, style = wx.TE_MULTILINE)
        
        splitter.SplitHorizontally(self.tree, self.textCtrl)
        splitter.SetMinimumPaneSize(40)
        splitter.SetSashPosition(250, True)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(tb, 0, wx.EXPAND)
        sizer.Add(splitter, 1, wx.EXPAND)
        self.SetSizer(sizer)

        self.imageList = wx.ImageList(22, 22)
        self.IM_OK = self.imageList.Add(ICON_OK)
        self.IM_NOK = self.imageList.Add(ICON_NOK)
        self.IM_DEFAULT = self.imageList.Add(ICON_DEFAULT)
        self.tree.SetImageList(self.imageList)

        wx.EVT_MENU(self, ID_LOAD, self.OnLoad)
        wx.EVT_MENU(self, ID_ABOUT, self.OnAbout)
        wx.EVT_MENU(self, ID_TB, self.OnTB)
        wx.EVT_CLOSE(self, self.OnExit)
        wx.EVT_TREE_ITEM_ACTIVATED(self, wx.ID_ANY, self.OnActivate)
        self.Bind(wx.EVT_TOOL, self.OnStart, id = ID_START)
        self.Bind(wx.EVT_TOOL, self.OnStopRequest,  id = ID_STOP)
        self.Bind(wx.EVT_TOOL, self.OnClear,  id = ID_CLEAR)

        self.Bind(EVT_TESTRESULT, self.OnTestResult)
        self.Bind(EVT_STOP, self.OnStop)
        self.Bind(EVT_ITEMTEXT, self.OnItemText)
        self.Bind(EVT_CONSOLE, self.OnConsole)

        if options and options.run:
            self.Load()
            self.OnStart()

    def OnTB(self, event):
        self.tb.Show(event.Checked())
        self.GetSizer().Layout()

    def OnTestResult(self, event):
        if not event.item.IsOk():
            print "!IsOk()..."
            return
        self.tree.SetItemImage(event.item, event.image)

    def OnItemText(self, event):
        if not event.item.IsOk():
            print "!IsOk()..."
            return
        if event.running:
            self.tree.SetItemText(event.item, self.tree.GetItemText(event.item) +  " Running...")
        else:
            self.tree.SetItemText(event.item, self.tree.GetItemText(event.item)[:-11])

    def OnConsole(self, event):
        """Add text to the console area. """
        self.textCtrl.AppendText(event.text)

    def OnExit(self, event):
        """Destroy the window."""
        self.Destroy()

    def OnActivate(self, event):
        """Tree item activated."""
        self.RunItem(event.GetItem())
    
    def OnLoad(self, event=None):
        global filename
        if RunDepth > 0:
            wx.MessageBox("Please stop any running tests first.", "")
            return
        dlg = wx.FileDialog(self, "Choose a module", ".", "", "*.py", wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            filename = dlg.GetPath()
            self.Load()
        
    def OnAbout(self, event = None):
        """Show the about box."""
        wx.MessageBox("PyTong " + VERSION + "\n2009, Grondwerk IT", "About...")

    def OnStart(self, event = None):
        """Start button is pressed."""
        item = self.tree.GetSelection()
        if not item.IsOk():
            item = self.tree.GetRootItem()
        if item.IsOk():
            self.RunItem(item)

    def OnStopRequest(self, event):
        global ShouldStop
        ShouldStop = True
        self.SetStatusText("Stopping tests...")

    def OnStop(self, event):
        self.Stop()

    def OnClear(self, event):
        self.textCtrl.Clear()
        if filename:
            self.Load()
    
    def Load(self):
        """ Loads the test class in filename. """
        f = os.path.abspath(filename)
        if not os.path.exists(f) or not os.path.isfile(f):
            self.textCtrl.AppendText("File not found: %s\n" % f)
            return
        # add script directory to search path and set it to current directory
        sys.path.append(os.path.dirname(f))
        os.chdir(os.path.dirname(f))
        modname = os.path.splitext(os.path.basename(f))[0]
        module = imp.load_source(modname, f, file(f))
        suite = unittest.defaultTestLoader.loadTestsFromModule(module)
        if suite._tests == []:
            wx.MessageBox("No unit tests could be loaded from: %s module" % filename, "No unit tests found", wx.ICON_ERROR)
            return
        if self.tree.GetRootItem().IsOk():
            self.tree.Delete(self.tree.GetRootItem())
        else:
            print "(not ok)"
        root = self.tree.AddRoot("Tests")
        self.tree.SetItemImage(root, self.IM_DEFAULT)
        self.AddSuite(suite, root)
        self.tree.ExpandAll()
        return True

    def AddSuite(self, suite, root):
        for s in suite:
            if isinstance(s, unittest.TestSuite):
                item = self.tree.AppendItem(root, s.__class__.__name__)
                self.tree.SetItemImage(item, self.IM_DEFAULT)
                self.tree.SetPyData(item, s)
                self.AddSuite(s, item)
            else:
                item = self.tree.AppendItem(root, "%s" % s)
                self.tree.SetItemImage(item, self.IM_DEFAULT)
                self.tree.SetPyData(item, s)

    def Stop(self):
        global ShouldStop
        self.SetMode(False)
        ShouldStop = False

    def SetMode(self, running):
        """If True, tests are running (e.g. run button is disabled), if False, tests are stopped."""
        self.running = running
        self.tb.EnableTool(ID_START, not running)
        self.menuTests.Enable(ID_START, not running)
        self.tb.EnableTool(ID_STOP, running)
        self.menuTests.Enable(ID_STOP, running)
        self.tb.EnableTool(ID_CLEAR, not running)
        self.menuTests.Enable(ID_CLEAR, not running)


    def RunItem(self, item):
        if RunDepth > 0:
            wx.MessageBox("Already running a test!", "")
            return
        self.SetMode(True)
        t = threading.Thread(target = lambda: RunTest(self, item))
        t.start()

class App(wx.App):
    """Application class"""
    def OnInit(self):
        """Overrides the wx.App.OnInit method."""
        frame = Frame("PyTong " + VERSION)
        frame.Show()
        return True

if __name__ == '__main__':
    usage = "usage: %prog [options] [filename]"
    version = "%prog " + VERSION
    parser = OptionParser(usage = usage, version = version)
    parser.add_option("-r", "--run", dest = "run", \
            action = "store_true", default = False, help = "start running all tests on startup")
    (options, args) = parser.parse_args()
    if len(args) > 1:
        parser.error("Only one filename is allowed.")
    elif len(args) == 1:
        filename = args[0]

    app = App(False)
    app.MainLoop()

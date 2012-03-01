#!/usr/bin/env python

import sys, os
import wx
import wx.stc  as  stc
import wx.lib.scrolledpanel as scrolled
from wx.lib.wordwrap import wordwrap

from diffutil import FancySequenceMatcher


FACE1 = FACE2 = FACE3 = "Dejavu Sans Mono"
FACE_SIZE = 10
DEBUG = 1


class DiffSTC(stc.StyledTextCtrl):
    def __init__(self, parent, ID):
        stc.StyledTextCtrl.__init__(self, parent, ID)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)

    def OnDestroy(self, evt):
        # This is how the clipboard contents can be preserved after
        # the app has exited.
        wx.TheClipboard.Flush()
        evt.Skip()


    def GetValue(self):
        return self.GetText()
    
    def SetValue(self, value):
        self.SetText(value)


class PyDiff(wx.Frame):

    REPLACE_STYLE = 5
    INSERT_STYLE = 6
    DELETE_STYLE = 6
    BLANK_STYLE = 8
    INTRA_STYLE = 21


    def __init__(self, parent, title, fromfile, tofile, fromtext, totext):
        wx.Frame.__init__(self, parent, title=title, size=(500, 500),style=wx.DEFAULT_FRAME_STYLE|wx.NO_FULL_REPAINT_ON_RESIZE)

        #initialize settings
        self.modify = False
        self.activeLine = None

        self.initDiff(fromfile, tofile, fromtext, totext)

        #create GUI
        self.createMenu()
        self.createSplitters()
        self.createToolbar()
        self.sb = self.CreateStatusBar()
        self.sb.SetStatusText("Press F1 for help")
    
        #bind some application events
        self.Bind(wx.EVT_CLOSE, self.QuitApplication)
        #self.Bind(wx.EVT_SIZE, self.OnResize)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        
        #display
        self.Center()
        self.Show(True)
        self.Maximize()

        self.rightSWindow.Scroll(0,0)
        self.leftSWindow.Scroll(0,0)

    def initDiff(self, fromfile, tofile, fromtext=None, totext=None):
        self.leftFileName = fromfile
        self.rightFileName = tofile
        if fromtext is None:
            fromlines = open(fromfile, 'U').readlines()
        else:
            fromlines = fromtext.splitlines(1)
        if totext is None:
            tolines = open(tofile, 'U').readlines()
        else:
            tolines = totext.splitlines(1)
        self.diffTexts = fromlines,tolines

    def OnWheel(self, event):
        pos =  self.rightSWindow.GetScrollPos(0)
        
        if event.GetWheelRotation() > 0:
            self.rightSWindow.Scroll(0,pos-1)
            self.leftSWindow.Scroll(0,pos-1)
        else:
            self.rightSWindow.Scroll(0,pos+1)
            self.leftSWindow.Scroll(0,pos+1)

    def createSplitters(self):
        # Create the splitter window.
        splitter = wx.SplitterWindow(self)
        splitter.SetMinimumPaneSize(1)

        font = wx.Font(16, wx.SWISS, wx.NORMAL, wx.NORMAL)
        if sys.platform == "darwin":
          fontLines = wx.Font(FACE_SIZE-1, wx.DEFAULT, wx.NORMAL, wx.NORMAL, False, FACE3)
        else:
          fontLines = wx.Font(FACE_SIZE, wx.DEFAULT, wx.NORMAL, wx.NORMAL, False, FACE3)
    
        def createTextPanel(self, splitter, scrollCallback, filename):
            swindow = wx.ScrolledWindow(splitter)
            swindow.SetScrollbars(20,20,55,40)
            swindow.Scroll(0,0)
            swindow.Bind(wx.EVT_SCROLLWIN, scrollCallback)

            vbox = wx.BoxSizer(wx.VERTICAL)
            hbox = wx.BoxSizer(wx.HORIZONTAL)
            swindow.SetSizer(vbox)
            lbl = wx.StaticText(swindow, -1, filename, (-1, -1))
            linesLbl = wx.StaticText(swindow, -1, "1", (-1, -1), style=wx.ALIGN_RIGHT)
            linesLbl.SetFont(fontLines)
            lbl.SetFont(font)
            vbox.Add(lbl, 0, flag=wx.CENTER)
            view = DiffSTC(swindow, -1)
            vbox.Add(hbox, 1, flag=wx.EXPAND)
            hbox.Add(linesLbl, 0)
            hbox.Add(view, 1, flag=wx.EXPAND)
            return lbl, linesLbl, view, swindow
        
        self.rightLbl, self.rightLinesLbl, self.rightView, self.rightSWindow = createTextPanel(self, splitter, self.OnScrollRight, self.rightFileName)
        self.leftLbl, self.leftLinesLbl, self.leftView, self.leftSWindow = createTextPanel(self, splitter, self.OnScrollLeft, self.leftFileName)
        
        #create text
        self.populateText()
        self.rightViewOrig = self.rightView.GetValue()

        splitter.SplitVertically(self.leftSWindow, self.rightSWindow)
        splitter.SetSashPosition(250, True)
        self.splitter = splitter
        
        self.leftView.Bind(wx.EVT_SCROLLWIN, self.OnScrollLeft)
        self.last_left_pos = self.leftView.GetScrollPos(1)
        self.last_right_pos = self.rightView.GetScrollPos(1)
        self.leftView.SetUseVerticalScrollBar(False)
        self.rightView.SetUseVerticalScrollBar(False)
        self.leftView.Bind(wx.EVT_MOUSEWHEEL, self.OnWheel)
        self.rightView.Bind(wx.EVT_MOUSEWHEEL, self.OnWheel)       
        self.leftView.SetReadOnly(True)
        
        self.leftView.Bind(wx.EVT_LEFT_UP, self.OnMouseLeft)
        self.rightView.Bind(wx.EVT_LEFT_UP, self.OnMouseRight)


        self.rightView.Bind(wx.EVT_KEY_UP, self.OnKey)
        self.rightView.Bind(wx.EVT_KEY_DOWN, self.OnKey)

    def OnMouseLeft(self, event):
        curpos = self.leftView.GetCurrentPos()
        self.setActiveLine(self.leftView.LineFromPosition(curpos), noMove = True)
        event.Skip()

    def OnMouseRight(self, event):
        curpos = self.rightView.GetCurrentPos()
        self.setActiveLine(self.rightView.LineFromPosition(curpos), noMove = True)
        event.Skip()

    def OnKey(self, event):
        if self.rightView.GetValue() != self.rightViewOrig:
            self.modify = True
            self.rightLbl.SetLabel("* " + self.rightFileName)
        event.Skip()

    def OnScrollLeft(self, event):
        pos = event.GetPosition()
        #pos = self.leftSWindow.GetScrollPos(1)
        self.rightSWindow.Scroll(0,pos)
        event.Skip()

    def OnScrollRight(self, event):
        pos = event.GetPosition()
        self.leftSWindow.Scroll(0,pos)
        event.Skip()

    def createMenu(self):
        # Set up menu bar for the program.
        self.mainmenu = wx.MenuBar()                  # Create menu bar.

        menuNames = "File Edit Navigate View Help".split()
        menus = {}
        for menuName in menuNames:
            menu = wx.Menu()
            self.mainmenu.Append(menu, menuName)  # Add the project menu to the menu bar.
            menus[menuName] = menu
        
        menu = menus["File"]
        item = menu.Append(wx.ID_OPEN, '&Open\tCtrl+O', '')  # Append a new menu
        item = menu.Append(wx.ID_NEW, '&Save\tCtrl+S', '')
        self.Bind(wx.EVT_MENU, self.OnSave, item)  # Create and assign a menu event.
        item = menu.Append(wx.ID_EXIT, 'Save As\tCtrl+Shift+S', '')
        menu.AppendSeparator()
        item = menu.Append(wx.ID_EXIT, 'Reload', '')
        menu.AppendSeparator()
        item = menu.Append(wx.ID_EXIT, '&Quit\tCtrl+Q', '')
        self.Bind(wx.EVT_MENU, self.QuitApplication, item)  # Create and assign a menu event.

        menu = menus["Help"]
        item = menu.Append(-1, 'About wxPyDiff', '')
        self.Bind(wx.EVT_MENU, self.OnInfo, item)  # Create and assign a menu event.
        

        # Attach the menu bar to the window.
        self.SetMenuBar(self.mainmenu)

    def OnInfo(self, event):
        info = wx.AboutDialogInfo()
        info.Name = "wxPyDiff"
        info.Version = "0.1a"
        info.Copyright = "(C) 2009 Fred Lionetti"
        info.Description = wordwrap(
            "A simple cross-platform diff utility made from wxPython and difflib.",
            350, wx.ClientDC(self))
        info.WebSite = ("http://code.google.com/p/wxpydiff/", "wxPyDiff home page")
        info.Developers = [ "Fred Lionetti" ]

        info.License = wordwrap("LGPL", 500, wx.ClientDC(self))

        # Then we call wx.AboutBox giving it that info object
        wx.AboutBox(info)

    def createToolbar(self):
        TBFLAGS = ( wx.TB_HORIZONTAL| wx.NO_BORDER| wx.TB_FLAT
            #| wx.TB_TEXT
            #| wx.TB_HORZ_LAYOUT
            )
        tb = self.CreateToolBar( TBFLAGS )
        tsize = (16,16)
        bmp = wx.ArtProvider.GetBitmap
        tb.SetToolBitmapSize(tsize)
        buttons = [
                  ["Open", wx.ART_FILE_OPEN, "Open file", self.OnOpen],
                  ["Save", wx.ART_FILE_SAVE, "Save file", self.OnSave],
                  ["Reload", wx.ART_EXECUTABLE_FILE, "Reload files", self.OnOpen],
                  ["Undo", wx.ART_UNDO, "Undo last change", self.OnOpen],
                  ["Previous Difference", wx.ART_GO_UP, "Go to previous difference", self.OnUp],
                  ["Next Difference", wx.ART_GO_DOWN, "Go to next difference", self.OnDown],
                  ["Use theirs", wx.ART_GO_FORWARD, "Use theirs for current text block", self.OnUseTheirs],
                  #["Use mine", wx.ART_GO_BACK, "Use mine for current text block", self.OnOpen],
                  ["Help", wx.ART_HELP, "Display help", self.OnOpen],
                  ]

        for btn in buttons:
            name, art, help, cmd = btn
            id = wx.NewId()
            tb.AddLabelTool(id, name, bmp(art, wx.ART_TOOLBAR, tsize), shortHelp=name, longHelp=help)
            self.Bind(wx.EVT_TOOL, cmd, id=id)

        tb.Realize()

    def OnUseTheirs(self, event):
        if self.activeLine == None:
            return
        
        self.leftView.GotoLine(self.activeLine)
        lineText = self.leftView.GetCurLine()[0]
        self.rightView.GotoLine(self.activeLine)
        self.rightView.LineDelete()
        self.rightView.InsertText(self.rightView.GetCurrentPos(), lineText)

    def OnUp(self, event):
        if self.activeLine == None:
            self.activeLine = self.specialLines[0]
        
        self.specialLines.reverse()
        for specialLine in self.specialLines:
            if specialLine < self.activeLine:
                self.setActiveLine(specialLine)
                self.specialLines.reverse()
                return
        self.specialLines.reverse()
    
    def OnDown(self, event):
        if self.activeLine == None:
            self.activeLine = self.specialLines[0]
        
        for specialLine in self.specialLines:
            if specialLine > self.activeLine:
                self.setActiveLine(specialLine)
                return

    def OnSave(self, event):
        print "do save..."
        f = open(self.rightFileName, 'w')
        lastPos = self.rightView.GetLineEndPosition(self.rightView.GetLineCount())
        for i in range(lastPos):
            if self.rightView.GetStyleAt(i) != self.BLANK_STYLE:
                f.write(chr(self.rightView.GetCharAt(i)))
        f.close()
        
        print "do update..."
        self.doUpdate()
        
    def doUpdate(self):
        print "init diff..."
        self.initDiff()
        print "pop text..."
        self.populateText()
        print "done!"

    def populateText(self):
        # set default windows end-of-line mode (\r\n)
        self.leftView.SetEOLMode(wx.stc.STC_EOL_CRLF)
        self.rightView.SetEOLMode(wx.stc.STC_EOL_CRLF)
        
        self.leftView.StyleSetSpec(stc.STC_STYLE_DEFAULT, "size:%d,face:%s" % (FACE_SIZE, FACE3))
        self.rightView.StyleSetSpec(stc.STC_STYLE_DEFAULT, "size:%d,face:%s" % (FACE_SIZE, FACE3))

        self.leftView.StyleClearAll()
        self.rightView.StyleClearAll()
        
        leftText = ""
        rightText = ""
        pluses = []
        minuses = []
        blank_left = []
        blank_right = []
        lsublines = []
        rsublines = []
        leftBlank = 0
        rightBlank = 0
        lastCode = ""
        subtractions = []
        additions = []
        modifications = []

        self.leftView.StyleSetSpec(self.REPLACE_STYLE, "face:%s,fore:#000000,back:#FFFF00,size:%d" % (FACE3, FACE_SIZE))
        self.rightView.StyleSetSpec(self.REPLACE_STYLE, "face:%s,fore:#000000,back:#FFFF00,size:%d" % (FACE3, FACE_SIZE))

        self.leftView.StyleSetSpec(self.DELETE_STYLE, "face:%s,fore:#000000,back:#FF0000,size:%d" % (FACE3, FACE_SIZE))
        self.rightView.StyleSetSpec(self.INSERT_STYLE, "face:%s,fore:#000000,back:#00FF00,size:%d" % (FACE3, FACE_SIZE))

        self.leftView.StyleSetSpec(self.BLANK_STYLE, "face:%s,italic,fore:#000000,back:#BBBBBB,size:%d" % (FACE3, FACE_SIZE))
        self.rightView.StyleSetSpec(self.BLANK_STYLE, "face:%s,italic,fore:#000000,back:#BBBBBB,size:%d" % (FACE3, FACE_SIZE))

        self.leftView.StyleSetSpec(self.INTRA_STYLE, "face:%s,fore:#000000,back:#FDD017,size:%d" % (FACE3, FACE_SIZE))
        self.rightView.StyleSetSpec(self.INTRA_STYLE, "face:%s,fore:#000000,back:#FDD017,size:%d" % (FACE3, FACE_SIZE))

        lineNum = 0
        additionPos = []
        subtractionPos = []
        modificationPos = []
        intraAdds = []
        intraSubs = []
        lastSub = None
        lastAdd = None
        blankLeft = []
        blankRight = []
        n = 1
        a, b = self.diffTexts
        seq = FancySequenceMatcher(None,a, b)
        groups = seq.get_opcodes()

        for tag, alo, ahi, blo, bhi in groups:
            if tag == "equal":
                for line in b[blo:bhi]:
                    leftText += line
                    rightText += line
            elif tag == "insert":
                for line in b[blo:bhi]:
                    start = len(leftText)
                    leftText += " \n"
                    end = len(leftText)
                    blankLeft.append([start,end-start])
                    
                    start = len(rightText)
                    rightText += line
                    end = len(rightText)
                    additionPos.append([start,end-start, None])
                  
            elif tag == "delete":
                for line in a[alo:ahi]:
                    start = len(leftText)
                    leftText += line
                    end = len(leftText)
                    subtractionPos.append([start,end-start, None])

                    start = len(rightText)
                    rightText += "\n"
                    end = len(rightText)
                    blankRight.append([start,end-start])

            elif tag == "replace":
                if len(a[alo:ahi]) != len(b[blo:bhi]):
                    if DEBUG: import pdb; pdb.set_trace()
                    raise RuntimeError("Replace blocks doesn't have equal line quantities")

                for linea, lineb in zip(a[alo:ahi], b[blo:bhi]):
                    starta = len(leftText)
                    leftText += linea
                    end = len(leftText)
                    subtractionPos.append([starta,end-starta, True])
                    startb = len(rightText)
                    rightText += lineb
                    end = len(rightText)
                    additionPos.append([startb,end-startb, True])
                    for ai, bj in seq._intraline_diffs(linea, lineb):
                        intraSubs.append([starta + ai[0], ai[1] - ai[0], True])
                        intraAdds.append([startb + bj[0], bj[1] - bj[0], True])
            else:
                if DEBUG: import pdb; pdb.set_trace()
                raise RuntimeError("Diff operation unknown: %s" % tag)


        def updateLinesNumbers(ed, lbl, greyStyle):
            lines = ""
            i = 0
            for line in range(ed.GetLineCount()):
                if ed.GetStyleAt(ed.PositionFromLine(line)) != self.BLANK_STYLE:
                    i += 1
                    lines += "%d\n"%i
                    # TODO: use MARGINSETTEXT
                else:
                    lines += "\n"
            
            lbl.SetLabel(lines)
               
        def setupStyle(self, ed, marker, markerColor, linesLbl, blankLines, diffList, intraDiffs):
            ed.StartStyling(0, 0xff)
            styleid = 20
            ed.StyleSetSpec(styleid, "face:%s,fore:#000000,back:#FFFFFF,size:%d" % (FACE3, FACE_SIZE))
            ed.SetStyling(ed.GetLength(), styleid)
            markerStyleId = 2
            markerStyleIdMod = 4
            
            ed.MarkerDefine(markerStyleId, marker, markerColor, markerColor)
            ed.MarkerDefine(markerStyleIdMod, wx.stc.STC_MARK_CHARACTER+ord("!"), "dark yellow", "light gray")


            #add diffs and red minus signs
            for pos in diffList:
                start, delta, modified = pos
                ed.StartStyling(start, 0xff)
                if not modified:
                    ed.SetStyling(delta-1, self.INSERT_STYLE)
                    ed.MarkerAdd(ed.LineFromPosition(start), markerStyleId)
                else:
                    ed.SetStyling(delta-1, self.REPLACE_STYLE)
                    ed.MarkerAdd(ed.LineFromPosition(start), markerStyleIdMod)

            #add grey blank lines
            for pos in blankLines:
                start, delta = pos
                ed.StartStyling(start, 0xff)
                ed.SetStyling(delta, self.BLANK_STYLE)
                # TODO: use AnnotationSetText(1, "ann\n")

            # add in-line 
            for diffline in intraDiffs:
                start, delta, changed = diffline
                ed.StartStyling(start, 0xff)
                ed.SetStyling(delta, self.INTRA_STYLE)
            
            updateLinesNumbers(ed, linesLbl, self.BLANK_STYLE)
        
        self.leftView.SetValue(leftText)
        self.rightView.SetValue(rightText)
        setupStyle(self, self.leftView, stc.STC_MARK_MINUS, "red", self.leftLinesLbl, blankLeft, subtractionPos, intraSubs)
        setupStyle(self, self.rightView, stc.STC_MARK_PLUS, "blue", self.rightLinesLbl, blankRight, additionPos, intraAdds)
        
        self.calculateSpecialLines(subtractionPos, additionPos)

        self.leftView.EmptyUndoBuffer()
        self.rightView.EmptyUndoBuffer()

        self.arrowMarker = 3
        self.leftView.MarkerDefine(self.arrowMarker, stc.STC_MARK_ARROW, "black", "black")
        self.rightView.MarkerDefine(self.arrowMarker, stc.STC_MARK_ARROW, "black", "black")
        
        #self.setActiveLine(3)

    def calculateSpecialLines(self, subtractionPos, additionPos):
        specialLines = []
        specialPositions = [pos[0] for pos in subtractionPos]
        for line in specialPositions:
            specialLines.append(self.leftView.LineFromPosition(line))
        print "\n"
        specialPositions = [pos[0] for pos in additionPos]
        for line in specialPositions:
            specialLines.append(self.rightView.LineFromPosition(line))
        
        self.specialLines = list(set(specialLines))
        self.specialLines.sort()

    def setActiveLine(self, lineNum, noMove = False):
        if self.activeLine != None:
            self.leftView.MarkerDelete(self.activeLine, self.arrowMarker)
            self.rightView.MarkerDelete(self.activeLine, self.arrowMarker)
        self.leftView.MarkerAdd(lineNum, self.arrowMarker)
        self.rightView.MarkerAdd(lineNum, self.arrowMarker)
        self.activeLine = lineNum

        if not noMove:
            ratio = float(self.rightSWindow.GetScrollPageSize(1))/self.rightView.GetLineCount()
            self.rightSWindow.Scroll(0,self.activeLine*ratio)
            self.leftSWindow.Scroll(0,self.activeLine*ratio)

    def OnSize(self, event):
        xsize, ysize = event.GetSize()
        self.splitter.SetSashPosition(int(xsize/2), True)
        event.Skip()
        
    def OnOpen(self, event):
        print "not yet implemented!"

    def QuitApplication(self, event):
        if self.modify:
            dlg = wx.MessageDialog(self, 'Save before Exit?', '', wx.YES_NO | wx.YES_DEFAULT |
                        wx.CANCEL | wx.ICON_QUESTION)
            val = dlg.ShowModal()
            if val == wx.ID_YES:
                self.OnSaveFile(event)
                if not self.modify:
                    wx.Exit()
            elif val == wx.ID_CANCEL:
                dlg.Destroy()
            else:
                self.Destroy()
        else:
            self.Destroy()


if __name__ == '__main__':

    if len(sys.argv) > 2:
        fromfile = sys.argv[-2]
        tofile = sys.argv[-1]
    else:
        fromfile = "test2.txt"
        tofile = "test1.txt"
    app = wx.App(0)
    frame = PyDiff(None, 'wxPyDiff', fromfile, tofile)
    app.MainLoop()



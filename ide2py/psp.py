#!/usr/bin/env python
# coding:utf-8

"Personal Software Process (TM) Integrated & Automatic Metrics Collectotion"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"

# PSP Time Toolbar & Defect Log inspired by PSP Dashboard (java/open source)
# Most GUI classes are based on wxPython demos

# TODO General: further enhance MVC pattern

import sys
import wx
import wx.grid
from wx.lib.mixins.listctrl import CheckListCtrlMixin, ListCtrlAutoWidthMixin, TextEditMixin

import images

PSP_PHASES = ["Planning", "Design", "Code", "Compile", "Test", "Postmortem"]


class PlanSummaryTable(wx.grid.PyGridTableBase):
    "PSP Planning tracking summary (actual vs estimated)"
    def __init__(self, grid):
        wx.grid.PyGridTableBase.__init__(self)
        self.rows = PSP_PHASES
        self.cols = "Plan", "Actual"            
        self.cells = {}
        self.grid = grid
        
    def GetNumberRows(self):
        return len(self.rows)

    def GetNumberCols(self):
        return len(self.cols)

    def IsEmptyCell(self, row, col):
        return self.cells.get(row, {}).get(col, {}) and True or False

    def GetValue(self, row, col):
        val = self.cells.get(row, {}).get(col, 0)
        return val
        #return "%02d:%02d" % (val / 60, val % 60)

    def SetValue(self, row, col, value):
        self.cells.setdefault(row, {})[col] = value
        
    def GetColLabelValue(self, col):
        return self.cols[col]
       
    def GetRowLabelValue(self, row):
        return self.rows[row]

    def count(self, phase):
        "Increment actual user time according selected phase"
        row = PSP_PHASES.index(phase) 
        plan = self.GetValue(row, 0)
        value = self.GetValue(row, 1) + 1
        self.SetValue(row, 1, value)
        if plan:
            return value/float(plan) * 100
        self.UpdateValues(row)
        
    def UpdateValues(self, row):
        #msg = wx.grid.GridTableMessage(self,
        #    wx.grid.GRIDTABLE_REQUEST_VIEW_GET_VALUES,
        #    row, 1)
        #self.grid.ProcessTableMessage(msg)
        self.grid.ForceRefresh()
        #TODO: this doesn't work!

        
class DefectListCtrl(wx.ListCtrl, ListCtrlAutoWidthMixin, CheckListCtrlMixin): #TextEditMixin
    "Defect recording log facilities"
    def __init__(self, parent):
        wx.ListCtrl.__init__(self, parent, -1, style=wx.LC_REPORT)
        ListCtrlAutoWidthMixin.__init__(self)
        CheckListCtrlMixin.__init__(self)
        #TextEditMixin.__init__(self)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnItemActivated)
        self.data = []
        self.parent = parent
        self.InsertColumn(0, "Number", wx.LIST_FORMAT_RIGHT)
        self.InsertColumn(1, "Description")
        self.InsertColumn(2, "Date", wx.LIST_FORMAT_CENTER)
        self.InsertColumn(3, "Type")
        self.InsertColumn(4, "Inject")
        self.InsertColumn(5, "Remove")
        self.InsertColumn(6, "Fix Time", wx.LIST_FORMAT_RIGHT)
        self.InsertColumn(7, "Fix Defect")
        self.InsertColumn(8, "Filename")
        self.InsertColumn(9, "Line No.")
        self.InsertColumn(10, "Offset")
      
        self.SetColumnWidth(0, 50) #wx.LIST_AUTOSIZE)
        self.SetColumnWidth(1, 200) # wx.LIST_AUTOSIZE)
        #self.SetColumnWidth(2, 100)

        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnItemSelected, self)
        self.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.OnItemDeselected, self)
        
        self.selecteditemindex = None

    def AddItem(self, item):
        self.data.append(item+[False])
        index = self.InsertStringItem(sys.maxint, item[0])
        for i in range(1, len(item)):
            self.SetStringItem(index, i, str(item[i]))
        self.SetItemData(index, index)
            
    def OnItemActivated(self, evt):
        #self.ToggleItem(evt.m_itemIndex)
        event = self.data[ evt.m_itemIndex][8:11]
        self.parent.GotoFileLine(event,running=False)
        self.selecteditemindex = evt.m_itemIndex

    # this is called by the base class when an item is checked/unchecked
    def OnCheckItem(self, index, flag):
        row = self.GetItemData(index)
        title = self.data[row][0]
        if flag:
            what = "checked"
            col = 5 # update phase when removed 
            if not self.data[row][col]:
                phase = self.data[row][col] = self.parent.GetPSPPhase()
                self.SetStringItem(row, col, str(phase))
        else:
            what = "unchecked"
        self.data[row][-1] = flag
        
    def OnItemSelected(self, evt):
        pass ##print('item selected: %s\n' % evt.m_itemIndex)
        
    def OnItemDeselected(self, evt):
        pass ##print('item deselected: %s\n' % evt.m_itemIndex)
        
    def count(self, phase):
        "Increment actual user time to fix selected defect"
        if self.selecteditemindex is not None:
            row = self.selecteditemindex
            col = 6
            flag =  self.data[row][-1]
            if not flag:
                value = self.data[row][col] + 1
                self.data[row][col] = value
                self.SetStringItem(row, col, str(value))
        

class PSPMixin(object):
    "ide2py extension for integrated PSP support"
    
    def __init__(self):
        tb4 = self.CreatePSPToolbar()
        self._mgr.AddPane(tb4, wx.aui.AuiPaneInfo().
                          Name("tb4").Caption("PSP Toolbar").
                          ToolbarPane().Top().Row(1).Position(3).
                          LeftDockable(False).RightDockable(False).CloseButton(True))

        grid = self.CreatePSPPlanSummaryGrid()
        self._mgr.AddPane(grid, wx.aui.AuiPaneInfo().
                          Caption("PSP Plan Summary").
                          Layer(1).Position(2).
                          FloatingSize(wx.Size(300, 200)).CloseButton(True).MaximizeButton(True))
        self.psp_defect_list = self.CreatePSPDefectRecordingLog()
        self._mgr.AddPane(self.psp_defect_list, wx.aui.AuiPaneInfo().
                          Caption("PSP Defect Recording Log").
                          Bottom().Layer(2).Row(2).
                          FloatingSize(wx.Size(300, 200)).CloseButton(True).MaximizeButton(True))
        self._mgr.Update()

    def CreatePSPPlanSummaryGrid(self):
        grid = wx.grid.Grid(self)
        self.psptimetable = PlanSummaryTable(grid)
        grid.SetTable(self.psptimetable, True)
        return grid

    def CreatePSPDefectRecordingLog(self):
        list = DefectListCtrl(self)
        list.AddItem(["1", "defecto de prueba",  "hoy", "20", "code", "compile", 0, "", "","",""])
        return list
        
    def CreatePSPToolbar(self):
        ID_PLAY, ID_PAUSE, ID_STOP = [wx.NewId() for i in range(3)]
        tb4 = wx.ToolBar(self, -1, wx.DefaultPosition, wx.DefaultSize,
                         wx.TB_FLAT | wx.TB_NODIVIDER)
        tb4.SetToolBitmapSize(wx.Size(16, 16))

        text = wx.StaticText(tb4, -1, "PSP")
        tb4.AddControl(text)

        tb4.AddSimpleTool(ID_PLAY, images.play.GetBitmap(), "Start timer")
        tb4.AddSimpleTool(ID_PAUSE, images.pause.GetBitmap(), "Pause timer")
        tb4.AddSimpleTool(ID_PAUSE, images.stop.GetBitmap(), "Stop timer")
        
        self.psp_phase_choice = wx.Choice(tb4, -1, choices=PSP_PHASES)
        tb4.AddControl(self.psp_phase_choice)

        #wx.StaticText(self, -1, "Fase", (45, 15))
        self.psp_gauge = wx.Gauge(tb4, -1, 100, (50, 10))
        tb4.AddControl(self.psp_gauge)
        
        self.Bind(wx.EVT_TIMER, self.TimerHandler)
        self.timer = wx.Timer(self)

        self.Bind(wx.EVT_MENU, self.OnPlay, id=ID_PLAY)
        self.Bind(wx.EVT_MENU, self.OnStop, id=ID_PAUSE)
        self.Bind(wx.EVT_MENU, self.OnStop, id=ID_PAUSE)
        
        tb4.Realize()
        return tb4

    def GetPSPPhase(self):
        phase = self.psp_phase_choice.GetCurrentSelection()
        if phase>=0:
            return PSP_PHASES[phase]
        else:
            return ''

    def OnPlay(self, event):
        self.timer.Start(1000)

    def OnStop(self, event):
        self.timer.Stop()
    
    def TimerHandler(self, event):
        phase = self.GetPSPPhase()
        if phase:
            percent = self.psptimetable.count(phase)
            self.psp_gauge.SetValue(percent or 0)
            self.psp_defect_list.count(phase)
            
    def __del__(self):
        self.OnStop(None)

    def NotifyError(self, description="", type="20", filename=None, lineno=0, offset=0):
        no = str(len(self.psp_defect_list.data)+1)
        phase = self.GetPSPPhase()
        item = [no, description,  "hoy", type, phase, "", 0, "", filename, lineno, offset]
        self.psp_defect_list.AddItem(item)

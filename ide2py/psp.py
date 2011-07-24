﻿#!/usr/bin/env python
# coding:utf-8

"Personal Software Process (TM) Integrated & Automatic Metrics Collection"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"

# PSP Time Toolbar & Defect Log inspired by PSP Dashboard (java/open source)
# Most GUI classes are based on wxPython demos

import shelve
import sys
import wx
import wx.grid
from wx.lib.mixins.listctrl import CheckListCtrlMixin, ListCtrlAutoWidthMixin, TextEditMixin
import wx.lib.agw.aui as aui

import images

PSP_PHASES = ["Planning", "Design", "Code", "Compile", "Test", "Postmortem"]
PSP_TIMES = ["Plan", "Actual"]


class PlanSummaryTable(wx.grid.PyGridTableBase):
    "PSP Planning tracking summary (actual vs estimated)"
    def __init__(self, grid, filename="psp-summary.pkl"):
        wx.grid.PyGridTableBase.__init__(self)
        self.rows = PSP_PHASES
        self.cols = PSP_TIMES
        self.cells = shelve.open(filename, writeback=True)
        self.grid = grid
        self.UpdateValues()

    def __del__(self):
        self.cells.close()

    def GetNumberRows(self):
        return len(self.rows)

    def GetNumberCols(self):
        return len(self.cols)

    def IsEmptyCell(self, row, col):
        return self.cells.get(row, {}).get(col, {}) and True or False

    def GetValue(self, row, col):
        key_phase = PSP_PHASES[row]
        key_time = PSP_TIMES[col]
        val = self.cells.get(key_phase, {}).get(key_time, 0)
        return val
        #return "%02d:%02d" % (val / 60, val % 60)

    def SetValue(self, row, col, value):
        key_phase = PSP_PHASES[row]
        key_time = PSP_TIMES[col]
        self.cells.setdefault(key_phase, {})[key_time] = value
        self.cells.sync()
        
    def GetColLabelValue(self, col):
        return self.cols[col]
       
    def GetRowLabelValue(self, row):
        return self.rows[row]

    def count(self, phase):
        "Increment actual user time according selected phase"
        row = PSP_PHASES.index(phase)
        col = PSP_TIMES.index("Plan")
        plan = self.GetValue(row, col)
        col = PSP_TIMES.index("Actual")
        value = self.GetValue(row, col) + 1
        self.SetValue(row, col, value)
        #self.grid.SetCellValue(row, col, str(value))
        #self.grid.Refresh()
        self.UpdateValues(row)
        self.grid.SelectRow(row)
        if plan:
            return value/float(plan) * 100
        
    def UpdateValues(self, row=None):
        self.grid.BeginBatch()
        msg = wx.grid.GridTableMessage(self,
            wx.grid.GRIDTABLE_REQUEST_VIEW_GET_VALUES)
        self.grid.ProcessTableMessage(msg)
        self.grid.ForceRefresh()
        self.grid.EndBatch()

        
class DefectListCtrl(wx.ListCtrl, CheckListCtrlMixin, ListCtrlAutoWidthMixin): #TextEditMixin
    "Defect recording log facilities"
    def __init__(self, parent, filename="psp-defects.pkl"):
        wx.ListCtrl.__init__(self, parent, -1, style=wx.LC_REPORT)
        ListCtrlAutoWidthMixin.__init__(self)
        CheckListCtrlMixin.__init__(self)
        #TextEditMixin.__init__(self)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnItemActivated)
        self.parent = parent
        self.col_defs = {
            "number": (0, wx.LIST_FORMAT_RIGHT, 50),
            "description": (1, wx.LIST_FORMAT_LEFT, wx.LIST_AUTOSIZE),
            "date": (2, wx.LIST_FORMAT_CENTER, 75),
            "type": (3, wx.LIST_FORMAT_LEFT, 50),
            "inject_phase": (4, wx.LIST_FORMAT_LEFT, 75),
            "remove_phase": (5, wx.LIST_FORMAT_LEFT, 75),
            "fix_time": (6, wx.LIST_FORMAT_RIGHT, 75),
            "fix_defect": (7, wx.LIST_FORMAT_LEFT, 50),
            "filename": (8, wx.LIST_FORMAT_LEFT, 100),
            "lineno": (9, wx.LIST_FORMAT_RIGHT, 50),
            "offset": (10, wx.LIST_FORMAT_RIGHT, 50),
            }
        for col_key, col_def in sorted(self.col_defs.items(), key=lambda k: k[1][0]):
            col_name = col_key.replace("_", " ").capitalize()
            i = col_def[0]
            col_fmt, col_size = col_def[1:3]
            self.InsertColumn(i, col_name, col_fmt)
            self.SetColumnWidth(i, col_size)
            if col_size == wx.LIST_AUTOSIZE:
                self.setResizeColumn(i+1)

        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnItemSelected, self)
        self.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.OnItemDeselected, self)

        self.selecteditemindex = None

        self.data = shelve.open(filename, writeback=True)
        for key, item in self.data.items():
            self.AddItem(item, key)

    def __del__(self):
        self.data.close()

    def AddItem(self, item, key=None):
        if "_checked" not in item:
            item["_checked"] = False
        index = self.InsertStringItem(sys.maxint, item["number"])
        if key is None:
            key = str(index)
            self.data[key] = item
            self.data.sync()
        for col_key, col_def in self.col_defs.items():
            val = item.get(col_key, "")
            self.SetStringItem(index, col_def[0], str(val))
        self.SetItemData(index, long(key))
        if item["_checked"]:
            self.ToggleItem(index)
            
    def OnItemActivated(self, evt):
        #self.ToggleItem(evt.m_itemIndex)
        key = str(self.GetItemData(evt.m_itemIndex))
        item = self.data[key]
        event = item["filename"], item["lineno"], item["offset"]
        self.parent.GotoFileLine(event,running=False)
        self.selecteditemindex = evt.m_itemIndex

    # this is called by the base class when an item is checked/unchecked
    def OnCheckItem(self, index, flag):
        key = str(self.GetItemData(index))
        item = self.data[key]
        title = item["number"]
        if flag:
            what = "checked"
            col_key = 'remove_phase' # update phase when removed 
            col_index = self.col_defs[col_key][0]
            if not item[col_key]:
                phase = item[col_key] = self.parent.GetPSPPhase()
                self.SetStringItem(index, col_index, str(phase))
        else:
            what = "unchecked"
        item["_checked"] = flag
        self.data.sync()
        
    def OnItemSelected(self, evt):
        pass ##print('item selected: %s\n' % evt.m_itemIndex)
        
    def OnItemDeselected(self, evt):
        pass ##print('item deselected: %s\n' % evt.m_itemIndex)
        
    def count(self, phase):
        "Increment actual user time to fix selected defect"
        if self.selecteditemindex is not None:
            index = self.selecteditemindex
            key = str(self.GetItemData(index))
            col_key = "fix_time"
            col_index = self.col_defs[col_key][0]
            flag =  self.data[key]["_checked"]
            if not flag:
                value = self.data[key][col_key] + 1
                self.data[key][col_key] = value
                self.data.sync()
                self.SetStringItem(index, col_index, str(value))



class PSPMixin(object):
    "ide2py extension for integrated PSP support"
    
    def __init__(self):
        tb4 = self.CreatePSPToolbar()
        self._mgr.AddPane(tb4, aui.AuiPaneInfo().
                          Name("psp_toolbar").Caption("PSP Toolbar").
                          ToolbarPane().Top().Position(3).CloseButton(True))

        grid = self.CreatePSPPlanSummaryGrid()
        self._mgr.AddPane(grid, aui.AuiPaneInfo().
                          Caption("PSP Plan Summary").Name("psp_plan").
                          Bottom().Position(1).Row(2).
                          FloatingSize(wx.Size(200, 200)).CloseButton(True).MaximizeButton(True))
        self.psp_defect_list = self.CreatePSPDefectRecordingLog()
        self._mgr.AddPane(self.psp_defect_list, aui.AuiPaneInfo().
                          Caption("PSP Defect Recording Log").Name("psp_defects").
                          Bottom().Row(2).
                          FloatingSize(wx.Size(300, 200)).CloseButton(True).MaximizeButton(True))
        self._mgr.Update()

    def CreatePSPPlanSummaryGrid(self):
        grid = wx.grid.Grid(self)
        self.psptimetable = PlanSummaryTable(grid)
        grid.SetTable(self.psptimetable, True)
        return grid

    def CreatePSPDefectRecordingLog(self):
        list = DefectListCtrl(self)
        #list.AddItem(["1", "defecto de prueba",  "hoy", "20", "code", "compile", 0, "", "","",""])
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

    def NotifyDefect(self, description="", type="20", filename=None, lineno=0, offset=0):
        no = str(len(self.psp_defect_list.data)+1)
        phase = self.GetPSPPhase()
        item = {'number': no, 'description': description, "date": "hoy", 
            "type": type, "inject_phase": phase, "remove_phase": "", "fix_time": 0, 
            "fix_defect": "", 
            "filename": filename, "lineno": lineno, "offset": offset}

        self.psp_defect_list.AddItem(item)
   

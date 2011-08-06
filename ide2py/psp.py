#!/usr/bin/env python
# coding:utf-8

"Personal Software Process (TM) Integrated & Automatic Metrics Collection"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"

# PSP Time Toolbar & Defect Log inspired by PSP Dashboard (java/open source)
# Most GUI classes are based on wxPython demos

import datetime
import shelve
import sys
import uuid
import wx
import wx.grid
from wx.lib.mixins.listctrl import CheckListCtrlMixin, ListCtrlAutoWidthMixin, TextEditMixin
import wx.lib.agw.aui as aui

import images

PSP_PHASES = ["planning", "design", "code", "compile", "test", "postmortem"]
PSP_TIMES = ["plan", "actual", "interruption", "comments"]


def pretty_time(counter):
    "return formatted string of a time count in seconds (days/hours/min/seg)"
    # find time unit and convert to it
    for factor, unit in ((1., 's'), (60., 'm'), (3600., 'h')):
        if counter < (60 * factor):
            break
    # only print fraction if it is not an integer result
    if counter % factor:
        return "%0.2f %s" % (counter/factor, unit)
    else:
        return "%d %s" % (counter/factor, unit)

def parse_time(user_input):
    "analyze user input, return a time count number in seconds"
    # sanity checks on user input:
    user_input = str(user_input).strip().lower()
    if not user_input:
        return 0
    elif ' ' in user_input:
        user_time, user_unit = user_input.split()
    elif not user_input[-1].isdigit():
        user_time, user_unit = user_input[:-1], user_input[-1]
    else:
        user_time, user_unit = user_input, ""
    # find time unit and convert from it to seconds
    user_time = user_time.replace(",", ".")
    for factor, unit in ((1, 's'), (60, 'm'), (3600, 'h')):
        if unit == user_unit:
            break
    return float(user_time) * factor


class PlanSummaryTable(wx.grid.PyGridTableBase):
    "PSP Planning tracking summary (actual vs estimated)"
    def __init__(self, grid, filename="psp_summary.dat"):
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
        key_phase = PSP_PHASES[row]
        key_time = PSP_TIMES[col]
        return self.cells.get(key_phase, {}).get(key_time, {}) and True or False

    def GetValue(self, row, col):
        key_phase = PSP_PHASES[row]
        key_time = PSP_TIMES[col]
        val = self.cells.get(key_phase, {}).get(key_time, 0)
        if key_time != "comments":
            return pretty_time(val)
        elif val:
            return '; '.join(['%s %s' % (msg, pretty_time(delta)) 
                                for msg, delta in val])
        else:
            return ''

    def SetValue(self, row, col, value):    
        value = parse_time(value)
        key_phase = PSP_PHASES[row]
        key_time = PSP_TIMES[col]
        self.cells.setdefault(key_phase, {})[key_time] = value
        self.cells.sync()
        
    def GetColLabelValue(self, col):
        return self.cols[col].capitalize()
       
    def GetRowLabelValue(self, row):
        return self.rows[row].capitalize()

    def count(self, phase, interruption):
        "Increment actual user time according selected phase"
        key_phase = phase
        key_time = "plan"
        plan = self.cells.get(key_phase, {}).get(key_time, 0)
        if not interruption:
            key_time = "actual"
        else:
            key_time = "interruption"
        value = self.cells.get(phase, {}).get(key_time, 0) + 1
        self.cells.setdefault(key_phase, {})[key_time] = value
        self.cells.sync()
        row = PSP_PHASES.index(phase)
        self.UpdateValues(row)
        self.grid.SelectRow(row)
        if plan:
            return value/float(plan) * 100

    def comment(self, phase, message, delta):
        "Record the comment of an interruption in selected phase"
        key_phase = phase
        comments = self.cells.get(key_phase, {}).get('comments', [])
        comments.append((message, delta))
        self.cells[key_phase]['comments'] = comments
        self.cells.sync()
        row = PSP_PHASES.index(phase)
        self.UpdateValues(row)
        self.grid.SelectRow(row)
        
    def UpdateValues(self, row=None):
        self.grid.BeginBatch()
        msg = wx.grid.GridTableMessage(self,
            wx.grid.GRIDTABLE_REQUEST_VIEW_GET_VALUES)
        self.grid.ProcessTableMessage(msg)
        self.grid.ForceRefresh()
        self.grid.EndBatch()

        
class DefectListCtrl(wx.ListCtrl, CheckListCtrlMixin, ListCtrlAutoWidthMixin): #TextEditMixin
    "Defect recording log facilities"
    def __init__(self, parent, filename=""):
        wx.ListCtrl.__init__(self, parent, -1, style=wx.LC_REPORT)
        ListCtrlAutoWidthMixin.__init__(self)
        CheckListCtrlMixin.__init__(self)
        #TextEditMixin.__init__(self)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnItemActivated)
        self.parent = parent
        self.col_defs = {
            "number": (0, wx.LIST_FORMAT_RIGHT, 50),
            "description": (1, wx.LIST_FORMAT_LEFT, wx.LIST_AUTOSIZE),
            "date": (2, wx.LIST_FORMAT_CENTER, 80),
            "type": (3, wx.LIST_FORMAT_LEFT, 50),
            "inject_phase": (4, wx.LIST_FORMAT_LEFT, 75),
            "remove_phase": (5, wx.LIST_FORMAT_LEFT, 75),
            "fix_time": (6, wx.LIST_FORMAT_RIGHT, 75),
            "fix_defect": (7, wx.LIST_FORMAT_LEFT, 50),
            "filename": (8, wx.LIST_FORMAT_LEFT, 100),
            "lineno": (9, wx.LIST_FORMAT_RIGHT, 50),
            "offset": (10, wx.LIST_FORMAT_RIGHT, 50),
            "uuid": (11, wx.LIST_FORMAT_RIGHT, 50),
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
        self.key_map = {}  # pos -> key
        
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
            key = str(uuid.uuid1())
            item['uuid'] = key
            self.data[key] = item
            self.data.sync()
        for col_key, col_def in self.col_defs.items():
            val = item.get(col_key, "")
            if col_key == 'fix_time':
                val = pretty_time(val)
            else:
                val = str(val)
            self.SetStringItem(index, col_def[0], val)
        self.key_map[long(index)] = key
        self.SetItemData(index, long(index))
        if item["_checked"]:
            self.ToggleItem(index)
            
    def OnItemActivated(self, evt):
        #self.ToggleItem(evt.m_itemIndex)      
        pos = long(self.GetItemData(evt.m_itemIndex))
        key = self.key_map[pos]
        item = self.data[key]
        event = item["filename"], item["lineno"], item["offset"]
        self.parent.GotoFileLine(event,running=False)
        self.selecteditemindex = evt.m_itemIndex

    # this is called by the base class when an item is checked/unchecked
    def OnCheckItem(self, index, flag):
        pos = long(self.GetItemData(index))
        key = self.key_map[pos]
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
            pos = long(self.GetItemData(index))
            key = self.key_map[pos]
            col_key = "fix_time"
            col_index = self.col_defs[col_key][0]
            flag =  self.data[key]["_checked"]
            if not flag:
                value = self.data[key][col_key] + 1
                self.data[key][col_key] = value
                self.data.sync()
                self.SetStringItem(index, col_index, pretty_time(value))



class PSPMixin(object):
    "ide2py extension for integrated PSP support"
    
    def __init__(self):
        cfg = wx.GetApp().get_config("PSP")
        
        # shelves (persistent dictionaries)
        psp_defects = cfg.get("psp_defects", "psp_defects.dat")
        psp_times = cfg.get("psp_times", "psp_times.dat")
        psp_summary = cfg.get("psp_summary", "psp_summary.dat")

        # text recording logs
        psp_time_log = cfg.get("psp_time_log", "psp_time_log.txt")
        self.psp_time_log_file = open(psp_time_log, "a")
        psp_defect_log = cfg.get("psp_defect_log", "psp_defect_log.txt")
        self.psp_defect_log_file = open(psp_defect_log, "a")
        
        tb4 = self.CreatePSPToolbar()
        self._mgr.AddPane(tb4, aui.AuiPaneInfo().
                          Name("psp_toolbar").Caption("PSP Toolbar").
                          ToolbarPane().Top().Position(3).CloseButton(True))

        grid = self.CreatePSPPlanSummaryGrid(filename=psp_times)
        self._mgr.AddPane(grid, aui.AuiPaneInfo().
                          Caption("PSP Plan Summary Times").Name("psp_plan").
                          Bottom().Position(1).Row(2).
                          FloatingSize(wx.Size(200, 200)).CloseButton(True).MaximizeButton(True))
        self.psp_defect_list = self.CreatePSPDefectRecordingLog(filename=psp_defects)
        self._mgr.AddPane(self.psp_defect_list, aui.AuiPaneInfo().
                          Caption("PSP Defect Recording Log").Name("psp_defects").
                          Bottom().Row(2).
                          FloatingSize(wx.Size(300, 200)).CloseButton(True).MaximizeButton(True))
        self._mgr.Update()
        # flag for time not spent on psp task
        self.psp_interruption = None

    def CreatePSPPlanSummaryGrid(self, filename):
        grid = wx.grid.Grid(self)
        self.psptimetable = PlanSummaryTable(grid, filename)
        grid.SetTable(self.psptimetable, True)
        return grid

    def CreatePSPDefectRecordingLog(self, filename):
        list = DefectListCtrl(self, filename)
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
        tb4.AddCheckLabelTool(ID_PAUSE, "Pause", images.pause.GetBitmap(),
                                    shortHelp="Pause timer (interruption)")
        tb4.AddSimpleTool(ID_STOP, images.stop.GetBitmap(), "Stop timer")
        
        self.psp_phase_choice = wx.Choice(tb4, -1, choices=PSP_PHASES)
        tb4.AddControl(self.psp_phase_choice)

        #wx.StaticText(self, -1, "Fase", (45, 15))
        self.psp_gauge = wx.Gauge(tb4, -1, 100, (50, 10))
        tb4.AddControl(self.psp_gauge)
        
        self.Bind(wx.EVT_TIMER, self.TimerHandler)
        self.timer = wx.Timer(self)

        self.Bind(wx.EVT_MENU, self.OnPlay, id=ID_PLAY)
        self.Bind(wx.EVT_MENU, self.OnPause, id=ID_PAUSE)
        self.Bind(wx.EVT_MENU, self.OnStop, id=ID_STOP)
        
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

    def OnPause(self, event):
        # check if we are in a interruption delta or not:
        if self.psp_interruption is not None:
            dlg = wx.TextEntryDialog(self, 
                'Enter a comment for the time recording log:', 
                'Interruption', 'phone call')
            if dlg.ShowModal() == wx.ID_OK:
                phase = self.GetPSPPhase()
                message = dlg.GetValue()
                self.psptimetable.comment(phase, message, self.psp_interruption)
            dlg.Destroy()
            # disable interruption counter
            self.psp_interruption = None
        else:
            # start interruption counter
            self.psp_interruption = 0
            print "pausing!"

    def OnStop(self, event):
        self.timer.Stop()
    
    def TimerHandler(self, event):
        # increment interruption delta time counter (if any)
        if self.psp_interruption is not None:
            self.psp_interruption += 1
            print "psp_interruption", self.psp_interruption
        phase = self.GetPSPPhase()
        if phase:
            percent = self.psptimetable.count(phase, self.psp_interruption)
            self.psp_gauge.SetValue(percent or 0)
            if not self.psp_interruption:
                self.psp_defect_list.count(phase)
            
    def __del__(self):
        self.OnStop(None)

    def NotifyDefect(self, description="", type="20", filename=None, lineno=0, offset=0):
        no = str(len(self.psp_defect_list.data)+1)
        phase = self.GetPSPPhase()
        item = {'number': no, 'description': description, "date": datetime.date.today(), 
            "type": type, "inject_phase": phase, "remove_phase": "", "fix_time": 0, 
            "fix_defect": "", 
            "filename": filename, "lineno": lineno, "offset": offset}

        self.psp_defect_list.AddItem(item)


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
from wx.lib.mixins.listctrl import CheckListCtrlMixin, ListCtrlAutoWidthMixin
import wx.lib.agw.aui as aui
        
import images
import simplejsonrpc

PSP_PHASES = ["planning", "design", "code", "compile", "test", "postmortem"]
PSP_TIMES = ["plan", "actual", "interruption", "comments"]
PSP_DEFECT_TYPES = {10: 'Documentation', 20: 'Synax', 30: 'Build', 
    40: 'Assignment', 50: 'Interface',  60: 'Checking', 70: 'Data', 
    80: 'Function', 90: 'System', 100: 'Enviroment'}

PSP_EVENT_LOG_FORMAT = "%(timestamp)s %(uuid)s %(phase)s %(event)s %(comment)s"

ID_START, ID_PAUSE, ID_STOP, ID_CHECK, \
ID_DEFECT, ID_DEL, ID_DEL_ALL, ID_EDIT, ID_FIXED, ID_WONTFIX, ID_FIX, \
ID_PROJECT, ID_PROJECT_LABEL, ID_UP, ID_DOWN = [wx.NewId() for i in range(15)]

WX_VERSION = tuple([int(v) for v in wx.version().split()[0].split(".")])

def pretty_time(counter):
    "return formatted string of a time count in seconds (days/hours/min/seg)"
    # find time unit and convert to it
    if counter is None:
        return ""
    counter = int(counter)
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
        col = PSP_TIMES.index(key_time)
        self.UpdateValues(row, col)
        self.grid.SelectRow(-1)
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
        
    def UpdateValues(self, row=-1, col=-1):
        if not self.grid.IsCellEditControlEnabled():
            self.grid.BeginBatch()
            msg = wx.grid.GridTableMessage(self,
                wx.grid.GRIDTABLE_REQUEST_VIEW_GET_VALUES,
                    row, col)
            self.grid.ProcessTableMessage(msg)
            #self.grid.ForceRefresh()
            self.grid.EndBatch()

        
class DefectListCtrl(wx.ListCtrl, CheckListCtrlMixin, ListCtrlAutoWidthMixin):
    "Defect recording log facilities"
    def __init__(self, parent, filename=""):
        wx.ListCtrl.__init__(self, parent, -1, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
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

        # make a popup-menu
        self.menu = wx.Menu()
        self.menu.Append(ID_FIX, "Fix...")
        self.menu.Append(ID_EDIT, "Edit")
        self.menu.Append(ID_FIXED, "Fixed")
        self.menu.Append(ID_WONTFIX, "Wontfix")
        self.menu.Append(ID_DEL, "Delete")
        self.menu.Append(ID_DEL_ALL, "Delete All")
        self.Bind(wx.EVT_MENU, self.OnItemActivated, id=ID_FIX)
        self.Bind(wx.EVT_MENU, self.OnChangeItem, id=ID_FIXED)
        self.Bind(wx.EVT_MENU, self.OnChangeItem, id=ID_WONTFIX)
        self.Bind(wx.EVT_MENU, self.OnEditItem, id=ID_EDIT)
        self.Bind(wx.EVT_MENU, self.OnDeleteItem, id=ID_DEL)
        self.Bind(wx.EVT_MENU, self.OnDeleteAllItems, id=ID_DEL_ALL)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        # for wxMSW
        self.Bind(wx.EVT_COMMAND_RIGHT_CLICK, self.OnRightClick)
        # for wxGTK 
        self.Bind(wx.EVT_RIGHT_UP, self.OnRightClick)
        
        self.selected_index = None

    def __del__(self):
        self.data.close()

    def AddItem(self, item, key=None):
        # check for duplicates (if defect already exists, do not add again!)
        if key is None:
            for defect in self.data.values():
                if (defect["description"] == item["description"] and 
                    defect["date"] == item["date"] and 
                    defect["filename"] == item["filename"] and 
                    defect["lineno"] == item["lineno"] and 
                    defect["offset"] == item["offset"]):
                    key = defect['uuid']
                    self.parent.psp_log_event("dup_defect", uuid=key, comment=str(item))
                    return
        if "_checked" not in item:
            item["_checked"] = False
        index = self.InsertStringItem(sys.maxint, str(item["number"]))
        # calculate max number + 1
        if item['number'] is None:
            if self.data:
                numbers = [int(defect['number'] or 0) for defect in self.data.values()]
                item['number'] = str(max(numbers) + 1)
            else:
                item['number'] = 1
        # create a unique string key to store it
        if key is None:
            key = str(uuid.uuid1())
            item['uuid'] = key
            self.data[key] = item
            self.data.sync()
            self.parent.psp_log_event("new_defect", uuid=key, comment=str(self.data[key]))
        for col_key, col_def in self.col_defs.items():
            val = item.get(col_key, "")
            if col_key == 'fix_time':
                val = pretty_time(val)
            elif val is not None:
                val = str(val)
            else:
                val = ""
            self.SetStringItem(index, col_def[0], val)
        self.key_map[long(index)] = key
        self.SetItemData(index, long(index))
        if item["_checked"]:
            self.ToggleItem(index)

    def OnRightClick(self, event):
        self.PopupMenu(self.menu)
            
    def OnItemActivated(self, evt):
        #self.ToggleItem(evt.m_itemIndex)      
        pos = long(self.GetItemData(evt.m_itemIndex))
        key = self.key_map[pos]
        item = self.data[key]
        event = item["filename"], item["lineno"], item["offset"]
        if item["filename"]:
            self.parent.GotoFileLine(event,running=False)
        self.selecteditemindex = evt.m_itemIndex
        self.parent.psp_log_event("activate_defect", uuid=key)

    def OnChangeItem(self, event):
        "Change item status -fixed, wontfix-"
        wontfix = event.GetId() == ID_WONTFIX
        self.OnCheckItem(self.selected_index, True, wontfix)
        self.ToggleItem(self.selected_index)

    # this is called by the base class when an item is checked/unchecked
    def OnCheckItem(self, index, flag, wontfix=False):
        pos = long(self.GetItemData(index))
        key = self.key_map[pos]
        item = self.data[key]
        title = item["number"]
        if item.get("_checked") != flag:
            if wontfix:
                item["fix_time"] = None
                col_key = 'fix_time' # clean fix time (wontfix mark)
                col_index = self.col_defs[col_key][0]
                self.SetStringItem(index, col_index, "")
            if flag:
                what = "checked"
                col_key = 'remove_phase' # update phase when removed 
                col_index = self.col_defs[col_key][0]
                if not item[col_key]:
                    phase = item[col_key] = self.parent.GetPSPPhase()
                    self.SetStringItem(index, col_index, str(phase))
            else:
                what = "unchecked"
            self.parent.psp_log_event("%s_defect" % what, uuid=key)
            item["_checked"] = flag
            self.data.sync()

    def OnKeyDown(self, event):
        key = event.GetKeyCode()
        control = event.ControlDown()
        #shift=event.ShiftDown()
        alt = event.AltDown()
        if key == wx.WXK_DELETE:
            self.OnDeleteItem(event)
        else:
            event.Skip()

    def OnDeleteItem(self, evt):
        if self.selected_index is not None:
            pos = long(self.GetItemData(self.selected_index))
            key = self.key_map[pos]
            del self.data[key]
            self.DeleteItem(self.selected_index)
            self.data.sync()
            # refresh new selected item
            if not self.data:
                self.selected_index = None
            elif self.selected_index == len(self.data):
                self.selected_index = len(self.data) - 1
            if self.selected_index is not None:
                self.Select(self.selected_index)

    def OnDeleteAllItems(self, evt):
        dlg = wx.MessageDialog(self, "Delete all defects?", "PSP Defect List",
                               wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
        if dlg.ShowModal() == wx.ID_YES:
            self.DeleteAllItems()
        dlg.Destroy()
            
    def OnEditItem(self, evt):
        pos = long(self.GetItemData(self.selected_index))
        key = self.key_map[pos]
        item = self.data[key]
 
        dlg = DefectDialog(None, -1, "Edit Defect No. %s" % item['number'], 
                           size=(350, 200), style=wx.DEFAULT_DIALOG_STYLE, )
        dlg.CenterOnScreen()
        dlg.SetValue(item)
        if dlg.ShowModal() == wx.ID_OK:
            item.update(dlg.GetValue())
            self.UpdateItem(self.selected_index, item)
        self.data[key] = item
        self.data.sync()

    def UpdateItem(self, index, item):
        for col_key, col_def in self.col_defs.items():
            val = item.get(col_key, "")
            if col_key == 'fix_time':
                val = pretty_time(val)
            elif val is not None:
                val = str(val)
            else:
                val = ""
            self.SetStringItem(index, col_def[0], val)

    def DeleteAllItems(self):
        for key in self.data:
            del self.data[key]
        self.data.sync()
        self.selected_index = None
        wx.ListCtrl.DeleteAllItems(self)
       
    def OnItemSelected(self, evt):
        self.selected_index = evt.m_itemIndex
        
    def OnItemDeselected(self, evt):
        self.selected_index = None
        
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
        

class DefectDialog(wx.Dialog):
    def __init__(self, parent, ID, title, size=wx.DefaultSize, 
            pos=wx.DefaultPosition, style=wx.DEFAULT_DIALOG_STYLE, ):

        wx.Dialog.__init__(self, parent, ID, title, size=size, pos=pos, style=style)

        sizer = wx.BoxSizer(wx.VERTICAL)

        self.label = wx.StaticText(self, -1, "Defect Nº - date - UUID")
        sizer.Add(self.label, 0, wx.ALIGN_CENTRE, 10)

        grid1 = wx.FlexGridSizer( 0, 2, 5, 5 )

        label = wx.StaticText(self, -1, "Description:")
        grid1.Add(label, 0, wx.ALIGN_LEFT, 5)
        self.description = wx.TextCtrl(self, -1, "", size=(200, 100), 
                                       style=wx.TE_MULTILINE)
        grid1.Add(self.description, 1, wx.EXPAND, 5)

        self.types = sorted(PSP_DEFECT_TYPES.keys())
        self.phases = phases = [""] + PSP_PHASES
        types = ["%s: %s" % (k, PSP_DEFECT_TYPES[k]) for k in self.types]
        
        label = wx.StaticText(self, -1, "Defect Type:")
        grid1.Add(label, 0, wx.ALIGN_LEFT, 5)
        self.defect_type = wx.Choice(self, -1, choices=types, size=(80,-1))
        grid1.Add(self.defect_type, 1, wx.EXPAND, 5)

        label = wx.StaticText(self, -1, "Inject Phase:")
        grid1.Add(label, 0, wx.ALIGN_LEFT, 5)
        self.inject_phase = wx.Choice(self, -1, choices=phases, size=(80,-1))
        grid1.Add(self.inject_phase, 1, wx.EXPAND, 5)

        label = wx.StaticText(self, -1, "Remove Phase:")
        grid1.Add(label, 0, wx.ALIGN_LEFT, 5)
        self.remove_phase = wx.Choice(self, -1, choices=phases, size=(80,-1))
        grid1.Add(self.remove_phase, 1, wx.EXPAND, 5)

        label = wx.StaticText(self, -1, "Fix time:")
        grid1.Add(label, 0, wx.ALIGN_LEFT, 5)
        self.fix_time = wx.TextCtrl(self, -1, "", size=(80,-1))
        grid1.Add(self.fix_time, 1, wx.ALIGN_LEFT, 5)

        label = wx.StaticText(self, -1, "Fix defect:")
        grid1.Add(label, 0, wx.ALIGN_LEFT, 5)
        self.fix_defect = wx.TextCtrl(self, -1, "", size=(80,-1))
        grid1.Add(self.fix_defect, 1, wx.ALIGN_LEFT, 5)

        sizer.Add(grid1, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        btnsizer = wx.StdDialogButtonSizer()
               
        btn = wx.Button(self, wx.ID_OK)
        btn.SetDefault()
        btnsizer.AddButton(btn)

        btn = wx.Button(self, wx.ID_CANCEL)
        btnsizer.AddButton(btn)
        btnsizer.Realize()

        sizer.Add(btnsizer, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        self.SetSizer(sizer)
        sizer.Fit(self)

    def SetValue(self, item):
        self.label.SetLabel(str(item.get("date", "")))
        self.description.SetValue(item.get("description", ""))
        if 'type' in item:
            self.defect_type.SetSelection(self.types.index(int(item['type'])))
        if 'inject_phase' in item:
            self.inject_phase.SetSelection(self.phases.index(item['inject_phase']))
        if 'remove_phase' in item:
            self.remove_phase.SetSelection(self.phases.index(item['remove_phase']))
        if 'fix_time' in item:
            self.fix_time.SetValue(pretty_time(item.get("fix_time", 0)))
        self.fix_defect.SetValue(item.get("fix_defect", "") or '')
        
    def GetValue(self):
        item = {"description": self.description.GetValue(), 
                "type": self.types[self.defect_type.GetCurrentSelection()], 
                "inject_phase": self.phases[self.inject_phase.GetCurrentSelection()],
                "remove_phase": self.phases[self.remove_phase.GetCurrentSelection()], 
                "fix_time": parse_time(self.fix_time.GetValue()), 
                "fix_defect": self.fix_defect.GetValue(), 
                }
        return item


class PSPMixin(object):
    "ide2py extension for integrated PSP support"
    
    def __init__(self):
        cfg = wx.GetApp().get_config("PSP")
        
        # shelves (persistent dictionaries)
        psp_defects = cfg.get("psp_defects", "psp_defects.dat")
        psp_times = cfg.get("psp_times", "psp_times.dat")
        psp_summary = cfg.get("psp_summary", "psp_summary.dat")

        # text recording logs
        psp_event_log_filename = cfg.get("psp_event_log", "psp_event_log.txt")
        self.psp_event_log_file = open(psp_event_log_filename, "a")
       
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

        # web2py json rpc client
        self.psp_rpc_client = simplejsonrpc.JSONRPCClient(cfg.get("server_url"))
        self.psp_project_name = cfg.get("project_name")
        if self.psp_project_name:
            self.psp_set_project(self.psp_project_name)

        self.Bind(wx.EVT_CHOICE, self.OnPSPPhaseChoice, self.psp_phase_choice)
        self.SetPSPPhase(cfg.get("current_phase"))


    def CreatePSPPlanSummaryGrid(self, filename):
        grid = wx.grid.Grid(self)
        self.psptimetable = PlanSummaryTable(grid, filename)
        grid.SetTable(self.psptimetable, True)
        return grid

    def CreatePSPDefectRecordingLog(self, filename):
        list = DefectListCtrl(self, filename)
        return list
        
    def CreatePSPToolbar(self):
        # old version of wx, dont use text text
        tb4 = aui.AuiToolBar(self, -1, wx.DefaultPosition, wx.DefaultSize,
                             wx.TB_FLAT | wx.TB_NODIVIDER)

        tsize = wx.Size(16, 16)
        GetBmp = lambda id: wx.ArtProvider.GetBitmap(id, wx.ART_TOOLBAR, tsize)
        tb4.SetToolBitmapSize(tsize)

        if WX_VERSION < (2, 8, 11): # TODO: prevent SEGV!
            tb4.AddSpacer(200)        
        tb4.AddLabel(-1, "PSP:", width=30)
        tb4.AddSimpleTool(ID_PROJECT, "Project", images.month.GetBitmap(),
                         short_help_string="Change current PSP Project")
        tb4.AddLabel(ID_PROJECT_LABEL, "select project...", width=100)

        tb4.AddSimpleTool(ID_UP, "Upload", GetBmp(wx.ART_GO_UP),
                          short_help_string="send metrics to remote server")
        tb4.AddSimpleTool(ID_DOWN, "Download", GetBmp(wx.ART_GO_DOWN),
                          short_help_string="receive metrics from remote server")

        
        tb4.AddSimpleTool(ID_START, "Start", images.record.GetBitmap(),
                         short_help_string="Start stopwatch (start phase)")
        tb4.AddCheckTool(ID_PAUSE, "Pause", images.pause.GetBitmap(), wx.NullBitmap,
                         short_help_string="Pause stopwatch (interruption)")
        tb4.AddSimpleTool(ID_STOP, "Stop", images.stop.GetBitmap(),
                          short_help_string="Stop stopwatch (finish phase)")

        tb4.EnableTool(ID_START, True)
        tb4.EnableTool(ID_PAUSE, False)
        tb4.EnableTool(ID_STOP, False)
        
        ##tb4.AddLabel(-1, "Phase:", width=50)
        self.psp_phase_choice = wx.Choice(tb4, -1, size=(150,-1), choices=PSP_PHASES + [""])
        if WX_VERSION > (2, 8, 11): # TODO: prevent SEGV!
            tb4.AddControl(self.psp_phase_choice, "PSP Phase")

        self.psp_gauge = wx.Gauge(tb4, -1, 100, (50, 8))
        if WX_VERSION > (2, 8, 11): # TODO: prevent SEGV!
            tb4.AddControl(self.psp_gauge, "Progressbar")

        tb4.AddSimpleTool(ID_DEFECT, "Defect", images.GetDebuggingBitmap(),
                          short_help_string="Add a PSP defect")
        tb4.AddSimpleTool(ID_CHECK, "Check", images.ok_16.GetBitmap(),
                          short_help_string="Check and finish phase")

        self.Bind(wx.EVT_TIMER, self.TimerHandler)
        self.timer = wx.Timer(self)

        self.Bind(wx.EVT_MENU, self.OnStartPSP, id=ID_START)
        self.Bind(wx.EVT_MENU, self.OnPausePSP, id=ID_PAUSE)
        self.Bind(wx.EVT_MENU, self.OnStopPSP, id=ID_STOP)
        self.Bind(wx.EVT_MENU, self.OnDefectPSP, id=ID_DEFECT)
        self.Bind(wx.EVT_MENU, self.OnProjectPSP, id=ID_PROJECT)
        self.Bind(wx.EVT_MENU, self.OnProjectPSP, id=ID_PROJECT_LABEL)
        self.Bind(wx.EVT_MENU, self.OnUploadProjectPSP, id=ID_UP)
        self.Bind(wx.EVT_MENU, self.OnDownloadProjectPSP, id=ID_DOWN)
        self.Bind(wx.EVT_MENU, self.OnCheckPSP, id=ID_CHECK)
        
        tb4.Realize()
        self.psp_toolbar = tb4

        return tb4

    def SetPSPPhase(self, phase):
        if phase:
            self.psp_phase_choice.SetSelection(PSP_PHASES.index(phase))
        else:
            self.psp_phase_choice.SetSelection(len(PSP_PHASES))

    def GetPSPPhase(self):
        phase = self.psp_phase_choice.GetCurrentSelection()
        if phase >= 0 and phase < len(PSP_PHASES):
            return PSP_PHASES[phase]
        else:
            return ''

    def OnPSPPhaseChoice(self, event):
        # store current phase in config file
        phase = self.GetPSPPhase()
        wx.GetApp().config.set('PSP', 'current_phase', phase)
        wx.GetApp().write_config()

    def OnStartPSP(self, event):
        self.timer.Start(1000)
        self.psp_log_event("start")
        self.psp_toolbar.EnableTool(ID_START, False)
        self.psp_toolbar.EnableTool(ID_PAUSE, True)
        self.psp_toolbar.EnableTool(ID_STOP, True)

    def OnPausePSP(self, event):
        # check if we are in a interruption delta or not:
        if self.psp_interruption is not None:
            dlg = wx.TextEntryDialog(self, 
                'Enter a comment for the time recording log:', 
                'Interruption', 'phone call')
            if dlg.ShowModal() == wx.ID_OK:
                phase = self.GetPSPPhase()
                message = dlg.GetValue()
                self.psptimetable.comment(phase, message, self.psp_interruption)
                self.psp_log_event("resuming", comment=message)
            dlg.Destroy()
            # disable interruption counter
            self.psp_interruption = None
        else:
            # start interruption counter
            self.psp_interruption = 0
            self.psp_log_event("pausing!")

    def OnStopPSP(self, event):
        self.timer.Stop()
        self.psp_log_event("stop")
        if self.psp_interruption: 
            self.OnPause(event)
            self.psp_toolbar.ToggleTool(ID_PAUSE, False)
        self.psp_toolbar.EnableTool(ID_START, True)
        self.psp_toolbar.EnableTool(ID_PAUSE, False)
        self.psp_toolbar.EnableTool(ID_STOP, False)
                    
    def TimerHandler(self, event):
        # increment interruption delta time counter (if any)
        if self.psp_interruption is not None:
            self.psp_interruption += 1
        phase = self.GetPSPPhase()
        if phase:
            percent = self.psptimetable.count(phase, self.psp_interruption)
            self.psp_gauge.SetValue(percent or 0)
            if not self.psp_interruption:
                self.psp_defect_list.count(phase)
            
    def __del__(self):
        self.OnStop(None)
        close(self.psp_event_log_file)
        
    def OnDefectPSP(self, event):
        dlg = DefectDialog(None, -1, "New Defect", size=(350, 200),
                         style=wx.DEFAULT_DIALOG_STYLE, 
                         )
        dlg.CenterOnScreen()
        dlg.SetValue({'inject_phase': self.GetPSPPhase()})
        if dlg.ShowModal() == wx.ID_OK:
            item = dlg.GetValue()
            item["date"] = datetime.date.today()
            item["number"] = None
            item["filename"] = item["lineno"] = item["offset"] = None
            self.psp_defect_list.AddItem(item)
        
    def NotifyDefect(self, description="", type="20", filename=None, lineno=0, offset=0):
        no = None
        phase = self.GetPSPPhase()
        item = {'number': no, 'description': description, "date": datetime.date.today(), 
            "type": type, "inject_phase": phase, "remove_phase": "", "fix_time": 0, 
            "fix_defect": "", 
            "filename": filename, "lineno": lineno, "offset": offset}

        self.psp_defect_list.AddItem(item)

    def psp_log_event(self, event, uuid="-", comment=""):
        phase = self.GetPSPPhase()
        timestamp = str(datetime.datetime.now())
        msg = PSP_EVENT_LOG_FORMAT % {'timestamp': timestamp, 'phase': phase, 
            'event': event, 'comment': comment, 'uuid': uuid}
        print msg
        self.psp_event_log_file.write("%s\r\n" % msg)
        self.psp_event_log_file.flush()

    def OnProjectPSP(self, event):
        "Fetch available projects, change to selected one and load/save metrics"
        try:
            projects = self.psp_rpc_client.get_projects()
        except Exception, e:
            projects = []
            dlg = wx.MessageDialog(self, u"Exception: %s\n\n" 
                       "Configure server_url in [PSP] section "
                       "and start web2py server" % unicode(e), 
                       "Cannot connect to psp2py application server!",
                       wx.OK | wx.ICON_EXCLAMATION)
            dlg.ShowModal()
            dlg.Destroy()

        dlg = wx.SingleChoiceDialog(self, 'Select a project', 'PSP Project',
                                    projects, wx.CHOICEDLG_STYLE)
        if dlg.ShowModal() == wx.ID_OK:
            self.psp_save_project()
            project_name = dlg.GetStringSelection()
            self.psp_load_project(project_name)
        dlg.Destroy()

    def OnUploadProjectPSP(self, event):
        self.psp_save_project()
    
    def OnDownloadProjectPSP(self, event):
        self.psp_load_project(self.psp_project_name)

    def psp_save_project(self):
        "Send metrics to remote server"
        # convert to plain dictionaries to be searialized and sent to web2py DAL
        # remove GUI implementation details, match psp2py database model
        dlg = wx.MessageDialog(self, "Send Metrics from remote site?",
                               "PSP Project Change", 
                               wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
        result = dlg.ShowModal() == wx.ID_YES
        dlg.Destroy()
        if result and self.psp_project_name:
            defects = []
            for defect in self.psp_defect_list.data.values():
                defect = defect.copy()
                defect['date'] = str(defect['date'])
                del defect['_checked']
                defects.append(defect)
            time_summaries = []
            comments = []
            for phase, times in self.psptimetable.cells.items():
                time_summary = {'phase': phase}
                time_summary.update(times)
                for message, delta in time_summary.pop('comments', []):
                    comment = {'phase': phase, 'message': message, 'delta': delta}
                    comments.append(comment)
                time_summaries.append(time_summary)
            self.psp_rpc_client.save_project(self.psp_project_name, defects, time_summaries, comments)
        return result
        
    def psp_load_project(self, project_name):
        "Receive metrics from remote server"
        # fetch and deserialize web2py rows to GUI data structures
        dlg = wx.MessageDialog(self, "Receive Metrics from remote site?", 
                               "PSP Project Change", 
                               wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
        result = dlg.ShowModal() == wx.ID_YES
        dlg.Destroy()
        if result:
            defects, time_summaries, comments = self.psp_rpc_client.load_project(project_name)
            self.psp_defect_list.DeleteAllItems()
            for defect in defects:
                defect["date"] = datetime.datetime.strptime(defect["date"], "%Y-%m-%d")
                self.psp_defect_list.AddItem(defect)
            self.psptimetable.cells.clear()
            for time_summary in time_summaries:
                self.psptimetable.cells[str(time_summary['phase'])] = time_summary
            for comment in comments:
                phase, message, delta = comment['phase'], comment['message'], comment['delta']
                self.psptimetable.comment(str(phase), message, delta)
            self.psptimetable.UpdateValues()
            self.psp_set_project(project_name)
        return result

    def psp_set_project(self, project_name):
        "Set project_name in toolbar and config file"
        self.psp_project_name = project_name
        self.psp_toolbar.SetToolLabel(ID_PROJECT_LABEL, project_name)
        self.psp_toolbar.Refresh()
        # store project name in config file
        wx.GetApp().config.set('PSP', 'project_name', project_name)
        wx.GetApp().write_config()

    def OnCheckPSP(self, event):
        "Finde defects and errors, if complete, change to the next phase"
        if self.active_child:
            phase = self.GetPSPPhase()
            defects = []    # static checks and failed tests
            errors = []     # sanity checks (planning & postmortem)
            if phase == "planning":
                # check plan summary completeness
                for phase, times in self.psptimetable.cells.items():
                    if not times['plan']:
                        errors.append("Complete %s estimate time!" % phase)
            elif phase == "design" or phase == "code":
                #TODO: review checklist?
                pass
            elif phase == "compile":
                # run "static" chekers to find coding defects (pep8, pyflakes)
                import checker
                defects.extend(checker.check(self.active_child.GetFilename()))
            elif phase == "test":
                # run doctests (TODO unittests, run program?) to find defects
                import tester
                defects.extend(tester.test(self.active_child.GetFilename()))
            elif phase == "postmortem":
                # check that all defects are fixed
                for defect in self.psp_defect_list.data.values():
                    if not defect['remove_phase']:
                        errors.append("Defect %(number)s not fixed!" % defect)

            # add found defects
            for defect in defects:
                self.NotifyDefect(**defect)
                errors.append("Defect found: %(description)s" % defect)

            # show errors
            if errors:
                dlg = wx.MessageDialog(self, "\n".join(errors), 
                       "PSP Check Phase Errors", wx.ICON_EXCLAMATION)
                dlg.ShowModal()
                dlg.Destroy()

            # phase completed? project completed?
            if not defects and not errors:
                i = PSP_PHASES.index(phase) + 1
                if i < len(PSP_PHASES):
                    phase = PSP_PHASES[i]
                else:
                    phase = ""
                self.OnStopPSP(event)
                self.SetPSPPhase(phase)


if __name__ == "__main__":
    app = wx.App()

    dlg = DefectDialog(None, -1, "Sample Dialog", size=(350, 200),
                     #style=wx.CAPTION | wx.SYSTEM_MENU | wx.THICK_FRAME,
                     style=wx.DEFAULT_DIALOG_STYLE, # & ~wx.CLOSE_BOX,
                     )
    dlg.CenterOnScreen()
    # this does not return until the dialog is closed.
    val = dlg.ShowModal()
    print dlg.GetValue()
    #dlg.Destroy()
    app.MainLoop()


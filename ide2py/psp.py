#!/usr/bin/env python
# coding:utf-8

"Personal Software Process (TM) Integrated & Automatic Metrics Collection"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"

# PSP Time Toolbar & Defect Log inspired by PSP Dashboard (java/open source)
# Most GUI classes are based on wxPython demos

import datetime
import os, os.path
import pickle, shelve
import sys
import hashlib, uuid
import wx
import wx.grid
from wx.lib.mixins.listctrl import CheckListCtrlMixin, ListCtrlAutoWidthMixin
import wx.lib.agw.aui as aui
        
import images
import simplejsonrpc


PSP_PHASES = ["planning", "design", "code", "review", "compile", "test", "postmortem"]
PSP_TIMES = ["plan", "actual", "interruption", "comments"]
PSP_DEFECT_TYPES = {10: 'Documentation', 20: 'Synax', 30: 'Build', 
    40: 'Assignment', 50: 'Interface',  60: 'Checking', 70: 'Data', 
    80: 'Function', 90: 'System', 100: 'Enviroment'}

PSP_EVENT_LOG_FORMAT = "%(timestamp)s %(uuid)s %(phase)s %(event)s %(comment)s"

ID_START, ID_PAUSE, ID_STOP, ID_CHECK, ID_METADATA, ID_DIFF, ID_PHASE, \
ID_DEFECT, ID_DEL, ID_DEL_ALL, ID_EDIT, ID_FIXED, ID_WONTFIX, ID_FIX, \
ID_PROJECT, ID_PROJECT_LABEL, ID_UP, ID_DOWN, ID_WIKI \
    = [wx.NewId() for i in range(19)]

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
            "summary": (1, wx.LIST_FORMAT_LEFT, wx.LIST_AUTOSIZE),
            "description": (1, wx.LIST_FORMAT_LEFT, 0),
            "date": (2, wx.LIST_FORMAT_CENTER, 80),
            "type": (3, wx.LIST_FORMAT_LEFT, 50),
            "inject_phase": (4, wx.LIST_FORMAT_LEFT, 75),
            "remove_phase": (5, wx.LIST_FORMAT_LEFT, 75),
            "fix_time": (6, wx.LIST_FORMAT_RIGHT, 75),
            "fix_defect": (7, wx.LIST_FORMAT_LEFT, 25),
            "filename": (8, wx.LIST_FORMAT_LEFT, 50),
            "lineno": (9, wx.LIST_FORMAT_RIGHT, 50),
            "offset": (10, wx.LIST_FORMAT_RIGHT, 0),
            "uuid": (11, wx.LIST_FORMAT_RIGHT, 0),
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
        defects = self.data.items()
        defects.sort(key=lambda d: int(d[1]['number']))
        for key, item in defects:
            self.AddItem(item, key)

        # make a popup-menu
        self.menu = wx.Menu()
        self.menu.Append(ID_EDIT, "Edit")
        self.menu.Append(ID_FIXED, "Mark Fixed")
        self.menu.Append(ID_WONTFIX, "Mark Wontfix")
        self.menu.Append(ID_DEL, "Delete")
        self.menu.Append(ID_DEL_ALL, "Delete All")
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
                if (defect["summary"] == item["summary"] and 
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
        event = item["filename"], item["lineno"], item["offset"] or 0
        if item["filename"] and item["lineno"]:
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

        label = wx.StaticText(self, -1, "Summary:")
        grid1.Add(label, 0, wx.ALIGN_LEFT, 5)
        self.summary = wx.TextCtrl(self, -1, "", size=(200, -1), )
        grid1.Add(self.summary, 1, wx.EXPAND, 5)

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
        self.summary.SetValue(item.get("summary", ""))
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
        item = {"summary": self.summary.GetValue(), 
                "description": self.description.GetValue(), 
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

        # metadata directory (convert to full path)
        self.psp_metadata_dir = cfg.get("metadata", "medatada")
        self.psp_metadata_dir = os.path.abspath(self.psp_metadata_dir)
        self.psp_metadata_cache = {}     # filename: (filestamp, metadata)
        if not os.path.exists(self.psp_metadata_dir):
            os.makedirs(self.psp_metadata_dir)

        # text recording logs
        psp_event_log_filename = cfg.get("psp_event_log", "psp_event_log.txt")
        self.psp_event_log_file = open(psp_event_log_filename, "a")

        self._current_psp_phase = None
       
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
        self.psp_rpc_client = simplejsonrpc.ServiceProxy(cfg.get("server_url"))
        self.psp_wiki_url = cfg.get("wiki_url")
        self.psp_project_name = cfg.get("project_name")
        if self.psp_project_name:
            self.psp_set_project(self.psp_project_name)

        self.Bind(wx.EVT_CHOICE, self.OnPSPPhaseChoice, self.psp_phase_choice)
        self.SetPSPPhase(cfg.get("current_phase"))

        self.CreatePSPMenu()
        
        # start up a browser on psp2py app
        url = cfg.get("psp2py_url")
        if False and url:
            import webbrowser
            wx.CallAfter(webbrowser.open, url)


    def CreatePSPPlanSummaryGrid(self, filename):
        grid = wx.grid.Grid(self)
        self.psptimetable = PlanSummaryTable(grid, filename)
        grid.SetTable(self.psptimetable, True)
        return grid

    def CreatePSPDefectRecordingLog(self, filename):
        list = DefectListCtrl(self, filename)
        return list

    def CreatePSPMenu(self):
        # create the menu items
        psp_menu = self.menu['psp'] = wx.Menu()
        psp_menu.Append(ID_PHASE, "Change PSP Phase")
        psp_menu.Append(ID_PROJECT, "Change Project")
        psp_menu.Append(ID_UP, "Upload metrics")
        psp_menu.Append(ID_DOWN, "Download metrics")
        psp_menu.AppendSeparator()
        psp_menu.Append(ID_START, "Start stopwatch")
        psp_menu.Append(ID_PAUSE, "Pause stopwatch\tPause")
        psp_menu.Append(ID_STOP, "Stop stopwatch")
        psp_menu.AppendSeparator()
        psp_menu.Append(ID_DEFECT, "Add Defect\tCtrl-D")
        psp_menu.Append(ID_CHECK, "Check Completion\tCtrl-F5")
        psp_menu.Append(ID_METADATA, "Show Metadata")
        psp_menu.Append(ID_DIFF, "Diff && Count LOC")
        self.menubar.Insert(self.menubar.FindMenu("&Help")-1, psp_menu, "&PSP")

        
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
        tb4.AddSimpleTool(ID_WIKI, "Help", images.gnome_help.GetBitmap(),
                          short_help_string="PSP Wiki")


        self.Bind(wx.EVT_TIMER, self.TimerHandler)
        self.timer = wx.Timer(self)

        self.Bind(wx.EVT_MENU, self.OnPhasePSP, id=ID_PHASE)
        self.Bind(wx.EVT_MENU, self.OnStartPSP, id=ID_START)
        self.Bind(wx.EVT_MENU, self.OnPausePSP, id=ID_PAUSE)
        self.Bind(wx.EVT_MENU, self.OnStopPSP, id=ID_STOP)
        self.Bind(wx.EVT_MENU, self.OnDefectPSP, id=ID_DEFECT)
        self.Bind(wx.EVT_MENU, self.OnProjectPSP, id=ID_PROJECT)
        self.Bind(wx.EVT_MENU, self.OnProjectPSP, id=ID_PROJECT_LABEL)
        self.Bind(wx.EVT_MENU, self.OnUploadProjectPSP, id=ID_UP)
        self.Bind(wx.EVT_MENU, self.OnDownloadProjectPSP, id=ID_DOWN)
        self.Bind(wx.EVT_MENU, self.OnCheckPSP, id=ID_CHECK)
        self.Bind(wx.EVT_MENU, self.OnMetadataPSP, id=ID_METADATA)
        self.Bind(wx.EVT_MENU, self.OnDiffPSP, id=ID_DIFF)
        self.Bind(wx.EVT_MENU, self.OnWikiPSP, id=ID_WIKI)
        
        tb4.Realize()
        self.psp_toolbar = tb4

        return tb4

    def set_current_psp_phase(self, phase):
        if self._current_psp_phase:
            print "Updating metadata", self._current_psp_phase, "->", phase
            self.UpdateMetadataPSP()
        self._current_psp_phase = phase
        
    def get_current_psp_phase(self):
        return self._current_psp_phase

    current_psp_phase = property(get_current_psp_phase, set_current_psp_phase)

    def SetPSPPhase(self, phase):
        if phase:
            self.psp_phase_choice.SetSelection(PSP_PHASES.index(phase))
        else:
            self.psp_phase_choice.SetSelection(len(PSP_PHASES))
        self.current_psp_phase = phase

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
        self.current_psp_phase = self.GetPSPPhase()

    def OnPhasePSP(self, event):
        "Event to change the current PSP phase"
        dlg = wx.SingleChoiceDialog(self, 'Select next phase', 'PSP Phase',
                                    PSP_PHASES, wx.CHOICEDLG_STYLE)
        if dlg.ShowModal() == wx.ID_OK:
            self.SetPSPPhase(dlg.GetStringSelection())
        dlg.Destroy()

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
            self.OnPausePSP(event)
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
        "Manually create a new PSP defect"
        dlg = DefectDialog(None, -1, "New Defect", size=(350, 200),
                         style=wx.DEFAULT_DIALOG_STYLE, 
                         )
        dlg.CenterOnScreen()
        phase = self.GetPSPPhase()
        filename = lineno = None
        # seek current file metadata for inject phase
        if self.active_child:
            filename = self.active_child.GetFilename()
            lineno = self.active_child.GetCurrentLine()
            if filename and lineno:
                metadata = self.update_metadata(filename)
                phase, line = metadata[lineno-1]
        dlg.SetValue({'inject_phase': phase})
        if dlg.ShowModal() == wx.ID_OK:
            item = dlg.GetValue()
            item["date"] = datetime.date.today()
            item["number"] = None
            item["filename"] = filename
            item["lineno"] = lineno
            item["offset"] = None
            self.psp_defect_list.AddItem(item)
        
    def NotifyDefect(self, summary="", type="20", filename=None, lineno=0, offset=0, description=""):
        no = None
        # if filename and line number, get injected psp phase from metadata
        if filename and lineno:
            metadata = self.update_metadata(filename)
            phase, line = metadata[lineno-1]
        else:
            phase = "" #self.GetPSPPhase()
        item = {'number': no, 'summary': summary, "date": datetime.date.today(), 
            "type": type, "inject_phase": phase, "remove_phase": "", "fix_time": 0, 
            "fix_defect": "", "description": description,
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
        "Send metrics to remote server (times and defects)"
        # convert to plain dictionaries to be searialized and sent to web2py DAL
        # remove GUI implementation details, match psp2py database model
        dlg = wx.MessageDialog(self, "Send Metrics to psp2py support app?",
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

    def psp_update_project(self, locs, objects):
        "Update metrics to remote server (only size now)"
        # convert to plain dictionaries to be searialized and sent to web2py DAL
        # remove GUI implementation details, match psp2py database model
        # this function is supposed to be called on postmortem phase (diff)
        dlg = wx.MessageDialog(self, "Update metrics into psp2py support app?",
                               "PSP Project Update", 
                               wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
        result = dlg.ShowModal() == wx.ID_YES
        dlg.Destroy()
        if result:
            # data received:
            # objects = [[7, 'Test', '__init__', 1, 'filename.py'], 
            # locs = {'new': 0, 'total': 6, 'modified': 1, 'comments': 1})
            #TODO: split new+modifed+reused loc count
            actual_loc = locs.get('new', 0) + locs.get('modified', 0)
            reuse_library_entries = []
            for obj in objects:
                entry = {
                    "filename": obj[4],
                    "class_name": obj[1],
                    "function_name": obj[2],
                    "lineno": obj[0],
                    "loc": obj[3],
                    }
                reuse_library_entries.append(entry)
            self.psp_rpc_client.update_project(self.psp_project_name, 
                                               actual_loc,
                                               reuse_library_entries)
        return result

    def psp_load_project(self, project_name):
        "Receive metrics from remote server (times and defects)"
        # fetch and deserialize web2py rows to GUI data structures
        dlg = wx.MessageDialog(self, "Receive Metrics from psp2py support app?", 
                               "PSP Project Change", 
                               wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
        result = dlg.ShowModal() == wx.ID_YES
        dlg.Destroy()
        if result:
            defects, time_summaries, comments = self.psp_rpc_client.load_project(project_name)
            self.psp_defect_list.DeleteAllItems()
            defects.sort(key=lambda defect: int(defect['number']))
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
        "Find defects and errors, if complete, change to the next phase"
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

            # add found defects (highlight them in the editor window)
            line_numbers = set()
            for defect in defects:
                self.NotifyDefect(**defect)
                errors.append("Defect found: %(summary)s" % defect)
                line_numbers.add(defect['lineno'])
            self.active_child.HighlightLines(line_numbers)

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
        else:
            dlg = wx.MessageDialog(self, "No active file, cannot check it.\n"
                    "Change PSP phase manually if desired.", 
                    "PSP Check Phase Errors", wx.ICON_EXCLAMATION)
            dlg.ShowModal()
            dlg.Destroy()

    def OnMetadataPSP(self, event):
        "Event to update and show metadata"
        self.UpdateMetadataPSP(show=True)

    def OnDiffPSP(self, event):
        "Event to calc diff and update metadata"
        # this is a temporary and auxiliar function just to rebuild metadata
        if self.active_child:
            import fileutil
            import locutil

            filename = self.active_child.GetFilename()
            if filename:
                with open(filename, "r") as f:
                    new_text, encoding, bom, eol, new_newlines = fileutil.unicode_file_read(f, "utf8")
        
            dlg = wx.TextEntryDialog(self, 'Compare with:', 
                'PSP DIFF', filename)
            if dlg.ShowModal() == wx.ID_OK:
                old_filename = dlg.GetValue()
                with open(old_filename, "r") as f:
                    old_text, encoding, bom, eol, old_newlines = fileutil.unicode_file_read(f, "utf8")
            else:
                old_filename = ''
                old_text = u''
                old_newlines = '\n'
            dlg.Destroy()

        # re-encode unicode to same encoding
        #old_text = old_text.encode("utf8")
        #new_text = new_text.encode("utf8")
        
        # render the diff
        from wxpydiff import PyDiff
        PyDiff(None, 'wxPyDiff (PSP)', old_filename, filename, old_text, new_text)

        # compare old and new lines:
        old_lines = old_text.split(old_newlines)
        new_lines = new_text.split(new_newlines)
        
        changes = locutil.analize_line_changes(old_lines, new_lines)
        objects, locs = locutil.count_logical_lines_per_object(filename, 
                                                               changes=changes)
        # add filename to each object (TODO: check several files)
        for obj in objects:
            obj.append(filename)

        # send metrics to remote server
        self.psp_update_project(locs, objects)
        
    def UpdateMetadataPSP(self, show=False):
        if self.active_child:
            filename = self.active_child.GetFilename()
            if filename:
                self.update_metadata(filename, show)
        
    def update_metadata(self, filename, show=False):
        import fileutil
        import diffutil
        
        # check if file was modified (cache stale):
        timestamp, metadata = self.psp_metadata_cache.get(filename, (None, None))
        if timestamp is None or timestamp != os.stat(filename).st_mtime:
            timestamp = os.stat(filename).st_mtime
            metadata = None

        # if not metadata valid in cached, rebuild it:
        if metadata is None:
            # read current text file and split lines
            with open(filename, "r") as f:
                text, encoding, bom, eol, newlines = fileutil.unicode_file_read(f, "utf8")
            # prepare new text lines
            new = text.split(newlines)
            # check to see if there is old metadata
            fn_hash = hashlib.sha224(filename).hexdigest()
            metadata_fn = os.path.join(self.psp_metadata_dir, "%s.dat" % fn_hash)
            if not os.path.exists(metadata_fn):
                # create metadata
                metadata = dict([(i, (self.current_psp_phase, l)) 
                                 for i, l in enumerate(new)])
            else:
                with open(metadata_fn, 'rb') as pkl:
                    old_metadata = pickle.load(pkl)
                # get old text lines
                old = [l for (phase, l) in old_metadata.values()]
                # compare new and old lines
                changes = diffutil.track_lines_changes(old, new)
                new_metadata = {}
                for old_lno, new_lno in changes:
                    if new_lno is not None and old_lno is None:
                        # new or replaced, change metadata
                        new_metadata[new_lno] = self.current_psp_phase , new[new_lno]
                    elif new_lno is not None and old_lno is not None:
                        # equal, maintain metadata
                        new_metadata[new_lno] = old_metadata[old_lno][0], new[new_lno]
                    else:
                        # deleted, do not copy to new metadata
                        pass 
                metadata = new_metadata
            with open(metadata_fn, 'wb') as pkl:
                pickle.dump(metadata, pkl)
    
            self.psp_metadata_cache[filename] = timestamp, metadata

        if show:
            msg = '\n'.join(["%10s - %s" % metadata[key] for key in sorted(metadata.keys())])
            dlg = wx.lib.dialogs.ScrolledMessageDialog(self, msg, "PSP METADATA")
            dlg.ShowModal()
            dlg.Destroy()

        return metadata


    def OnWikiPSP(self, event):
        # create the HTML "browser" window:
        ctrl = wx.html.HtmlWindow(self, -1, wx.DefaultPosition, wx.Size(400, 300))
        if "gtk2" in wx.PlatformInfo:
            ctrl.SetStandardFonts()
        ctrl.LoadPage(self.psp_wiki_url)
        self._mgr.AddPane(ctrl, aui.AuiPaneInfo().
                          Caption("PSP Wiki").
                          Float().
                          FloatingSize(wx.Size(300, 200)).MinimizeButton(True))
        self._mgr.Update()


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


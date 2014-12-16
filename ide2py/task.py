#!/usr/bin/env python
# coding:utf-8

"Task-focused interface integration to support context using activity history"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2014 Mariano Reingart"
__license__ = "GPL 3.0"


import datetime
import os, os.path
import sys
import uuid
import wx
import wx.grid
from wx.lib.mixins.listctrl import CheckListCtrlMixin, ListCtrlAutoWidthMixin
import wx.lib.agw.aui as aui
from wx.lib.scrolledpanel import ScrolledPanel

import connector
import images

DEBUG = False

ID_CREATE, ID_CHANGE, ID_DELETE, ID_SYNC, ID_TASK_LABEL, ID_CONTEXT = \
    [wx.NewId() for i in range(6)]

WX_VERSION = tuple([int(v) for v in wx.version().split()[0].split(".")])


class TaskMixin(object):
    "ide2py extension for integrated task-focused interface support"
    
    def __init__(self):
        
        cfg = wx.GetApp().get_config("TASK")
        self.task_id = None
        self.task_suspended = True
        
        # create the structure for the task-based database:
        self.db = wx.GetApp().get_db()
        self.db.create("task", task_id=int, task_name=str, task_uuid=str,
                               repo_path=str, closed=bool, status=str,
                               title=str, description=str, type=str,
                               resolution=str, owner=str, assignee=str,                               
                               started=str, completed=str, milestone=str,
                               connector=str, organization=str, project=str)    

        self.db.create("context_file", context_file_id=int, task_id=int, 
                                       filename=str, lineno=int, total_time=int,
                                       closed=bool)
        self.db.create("breakpoint", breakpoint_id=int, context_file_id=int, 
                                     lineno=int, temp=bool, cond=str)
        self.db.create("fold", fold_id=int, context_file_id=int, level=int, 
                               start_lineno=int, end_lineno=int, expanded=bool)
        
        # internal structure to keep tracking times and other 
        self.task_context_files = {}

        tb4 = self.CreateTaskToolbar()
        self._mgr.AddPane(tb4, aui.AuiPaneInfo().
                          Name("task_toolbar").Caption("Task Toolbar").
                          ToolbarPane().Top().Position(3).CloseButton(True))

        self._mgr.Update()

        self.AppendWindowMenuItem('Task',
            ('task_list', 'task_detail', 'task_toolbar', ), self.OnWindowMenu)
        
        self.task_panel = TaskPanel(self)
        self._mgr.AddPane(self.task_panel, aui.AuiPaneInfo().
                      Name("task_info").Caption("Task Info").
                      Layer(1).Position(2).BestSize(wx.Size(100, 300)).
                      Float().Position(5).CloseButton(True))
        self._mgr.Update()

        self.Bind(wx.EVT_MENU, self.OnChangeTask, id=ID_CHANGE)
        self.Bind(aui.EVT_AUITOOLBAR_TOOL_DROPDOWN, self.OnDropDownChangeTask, 
                  id=ID_CHANGE)
        self.Bind(wx.EVT_MENU, self.OnSyncTasks, id=ID_SYNC)

        self.CreateTaskMenu()

        # if configured, load the last task (later as PSP has to be initialized)
        task_id = cfg.get("task_id")
        if task_id:
            wx.CallAfter(lambda: self.activate_task(None, task_id))

    def CreateTaskMenu(self):
        # create the menu items
        task_menu = self.menu['task'] = wx.Menu()
        task_menu.Append(ID_CREATE, "Create Task")
        task_menu.Append(ID_CHANGE, "Change Task")
        task_menu.Append(ID_DELETE, "Delete Task")
        task_menu.Append(ID_SYNC, "Synchronize Tasks")
        task_menu.AppendSeparator()
        #task_menu.Append(ID_UP, "Upload activity")
        #task_menu.Append(ID_DOWN, "Download activity")
        task_menu.Append(ID_CONTEXT, "Show context")
        self.menubar.Insert(self.menubar.FindMenu("&Help")-1, task_menu, "&Task")
        
    def CreateTaskToolbar(self):
        # old version of wx, dont use text text
        tb4 = aui.AuiToolBar(self, -1, wx.DefaultPosition, wx.DefaultSize,
                             wx.TB_FLAT | wx.TB_NODIVIDER)

        tsize = wx.Size(16, 16)
        GetBmp = lambda id: wx.ArtProvider.GetBitmap(id, wx.ART_TOOLBAR, tsize)
        tb4.SetToolBitmapSize(tsize)

        if WX_VERSION < (2, 8, 11): # TODO: prevent SEGV!
            tb4.AddSpacer(200)        
        tb4.AddLabel(-1, "Task:", width=30)
        tb4.AddCheckTool(ID_CHANGE, "Task", images.month.GetBitmap(),
                         wx.NullBitmap, short_help_string="Change current Task")
        tb4.ToggleTool(ID_CHANGE, False)
        tb4.SetToolDropDown(ID_CHANGE, True)
        tb4.AddLabel(ID_TASK_LABEL, "create a task...", width=100)
        tb4.Realize()
        self.task_toolbar = tb4
        return tb4

    def OnChangeTask(self, event):
        "List available task, change to selected one and load/save context"
        tasks = self.db["task"].select(task_id=int, task_name=str, closed=False)
        fmt = "%(task_name)s [%(task_id)s]"
        tasks_dict = dict([(fmt % it, it["task_id"]) for it in tasks])
        dlg = wx.SingleChoiceDialog(self, 'Select a Task', 'Task Change',
                                    tasks_dict.keys(), wx.CHOICEDLG_STYLE)
        if dlg.ShowModal() == wx.ID_OK:
            task_name = dlg.GetStringSelection()
            task_id = tasks_dict[task_name]
            self.activate_task(task_name, task_id)
        dlg.Destroy()

    def OnDropDownChangeTask(self, event):

        if event.IsDropDownClicked():
            tb = event.GetEventObject()
            tb.SetToolSticky(event.GetId(), True)
            # create the popup menu
            popup = wx.Menu()
            m1 = wx.MenuItem(popup, wx.NewId(), "Suspend Task")
            popup.Bind(wx.EVT_MENU, lambda event: self.suspend_task(),
                      id=m1.GetId())
            popup.AppendItem(m1)
            m1.Enable(not self.task_suspended)
            m2 = wx.MenuItem(popup, wx.NewId(), "Resume Task")
            popup.Bind(wx.EVT_MENU, lambda event: self.resume_task(),
                      id=m2.GetId())
            popup.AppendItem(m2)
            m2.Enable(self.task_suspended)
            m3 = wx.MenuItem(popup, wx.NewId(), "Deactivate Task")
            popup.Bind(wx.EVT_MENU, lambda event: self.deactivate_task(),
                      id=m3.GetId())
            popup.AppendItem(m3)
            m3.Enable(bool(self.task_id))
            # line up our menu with the button
            rect = tb.GetToolRect(event.GetId())
            pt = tb.ClientToScreen(rect.GetBottomLeft())
            pt = self.ScreenToClient(pt)
            self.PopupMenu(popup, pt)
            # make sure the button is "un-stuck"
            tb.SetToolSticky(event.GetId(), False)


    def OnSyncTasks(self, event):
        "Retrieve available tasks and insert them in the local database"
        # get default project url
        cfg = wx.GetApp().get_config("TASK")
        url = cfg.get("URL") or "https://github.com/reingart/pyfactura"
        # ask
        dlg = wx.TextEntryDialog(
                self, 'Project URL',
                'Synchronize tasks', url)
        url = dlg.GetValue() if dlg.ShowModal() == wx.ID_OK else None
        dlg.Destroy()
        # remember url (TODO: list of used repositories?)
        if not url:
            return
        wx.GetApp().config.set("TASK", "URL", url)
        # sanity check:
        if not url.startswith("https://github.com/"):
            dlg = wx.MessageDialog(self, "URL not supported: %s\n" % url +
                                         "Only GitHub is supported right now.", 
                                         "Synchronize tasks",
               wx.OK | wx.ICON_INFORMATION)
            dlg.ShowModal()
            dlg.Destroy()  
            return
        # create a connector 
        cfg = wx.GetApp().get_config("GITHUB")
        kwargs = {}
        kwargs['username'] = cfg.get("username")
        kwargs['password'] = cfg.get("password")
        kwargs['organization'], kwargs['project'] = url.split("/")[3:5]
        gh = connector.GitHub(**kwargs)
        for data in gh.list_tasks():
            print data
            task = self.db["task"](task_name=data['name'], 
                                   organization=kwargs['organization'],
                                   project=kwargs['project'],
                                   description=data['description'],
                                   type=data['type'],
                                   resolution=data['resolution'],
                                   started=data['started'],
                                   owner=data['owner'], 
                                   status=data['status'], 
                                   ##assignee=data['assignee'],
                                   connector="github")
            if not task:
                # add the new task
                task = self.db["task"].new(task_name=data['name'], 
                                           task_uuid=str(uuid.uuid1()),
                                           connector="github",
                                           organization=kwargs['organization'],
                                           description=data['description'],
                                           type=data['type'],
                                           resolution=data['resolution'],
                                           started=data['started'],
                                           owner=data['owner'],
                                           status=data['status'], 
                                           ##assignee=data['assignee'],
                                           project=kwargs['project'])
                task.save()
            # update the task
            for k, v in data.items():
                if k in task.keys():
                    task[k] = v
            task['closed'] = data['status']=='closed'
            task.save()
        self.db.commit()

    def activate_task(self, task_name=None, task_id=None):
        "Set task name in toolbar and uuid in config file"
        # deactivate the current active task to update context if required:
        self.deactivate_task()
        if DEBUG: print "ACTIVATING TASK",  task_name, task_id
        if task_id:
            # get the task for a given id
            task = self.db["task"][task_id]
            task_name = task['task_name']
        elif task_name:
            # search the task using the given name
            task = self.db["task"](task_name=task_name)
            if not task:
                # add the new task
                task = self.db["task"].new(task_name=task_name, 
                                           task_uuid=str(uuid.uuid1()))
                task.save()
                self.db.commit()
        else:
            task = None

        self.set_task(task)
        if task:
            self.task_id = task['task_id']
            self.resume_task()
            if DEBUG: print "TASK ID", self.task_id, task.data_in
            self.preload_task(task)

    def set_task(self, task):
        task_id = task['task_id'] if task else None
        task_name = task['task_name'] if task else ""
        self.task_toolbar.SetToolLabel(ID_TASK_LABEL, task_name)
        self.task_toolbar.Refresh()
        if not wx.GetApp().closing:
            # store project name in config file
            if task_id:
                wx.GetApp().config.set('TASK', 'task_id', task_id)
            else:
                wx.GetApp().config.remove_option('TASK', 'task_id')
            wx.GetApp().write_config()
        self.task_id = task_id
            
    def preload_task(self, task):
        # pre-load all task contexts (open an editor if necessary):
        rows = self.db['context_file'].select(task_id=self.task_id)
        # sort in the most relevant order (max total_time, reversed):
        context_files = sorted(rows, key=lambda it: (-(it['total_time'] or 0)))
        first = None
        for row in context_files:
            filename = row['filename']
            if filename:
                ctx = self.get_task_context(filename)
                is_url = filename.startswith(("http://", "https://"))
                if not ctx['closed'] and (is_url or os.path.exists(filename)):
                    if first is None:
                        first = filename
                    self.DoOpen(filename)
        # activate editor of the most relevant context file:
        if first:
            self.DoOpen(first)
        # populate the repository view associated to this task:
        if task['repo_path']:
            # TODO: calculate a better fall-off relevancy limit
            relevance_threshold = 5
            wx.CallLater(2000, self.DoOpenRepo, task['repo_path'], 
                                                relevance_threshold)

        # create a connector and display the task panel
        if task['connector'] == 'github':
            cfg = wx.GetApp().get_config("GITHUB")
            kwargs = {}
            kwargs['username'] = cfg.get("username")
            kwargs['password'] = cfg.get("password")
            kwargs['organization'] = task['organization'] or cfg.get('username')
            kwargs['project'] = task['project'] or 'prueba'
            gh = connector.GitHub(**kwargs)
            # get the current panel, or create a new one:
            wx.CallLater(3000, self.task_panel.Load, gh, task)

    def deactivate_task(self):
        # store the opened repository to the current active task (if any):
        if DEBUG: print "DE-ACTIVATING TASK", self.task_id
        self.suspend_task()
        if self.task_id:
            task = self.db["task"][self.task_id]
            task['repo_path'] = self.repo_path
            # get data from task pane:
            self.task_panel.Save()
            task.save()
            self.db.commit()
        self.set_task(None)

    def suspend_task(self):
        if DEBUG: print "SUSPENDING TASK", self.task_id, self.task_suspended
        if self.task_id and not self.task_suspended:
            self.task_suspended = True
            self.task_toolbar.ToggleTool(ID_CHANGE, False)
            self.task_toolbar.Refresh(False)
            self.task_toolbar.Update()

    def resume_task(self):
        if DEBUG: print "RESUMING TASK", self.task_id, self.task_suspended
        if self.task_id and self.task_suspended:
            self.task_suspended = False
            self.task_toolbar.ToggleTool(ID_CHANGE, True)
            self.task_toolbar.Refresh(False)
            self.task_toolbar.Update()

    def get_task_context(self, filename):
        "Fetch the current record for this context file (or create a new one)"
        # check if it was already fetched from the db
        if filename in self.task_context_files:
            ctx = self.task_context_files[filename]
        else:
            ctx = self.db["context_file"](task_id=self.task_id, filename=filename)
            if not ctx:
                # insert the new context file to this task
                ctx = self.db["context_file"].new(task_id=self.task_id, 
                                                  filename=filename)
            self.task_context_files[filename] = ctx
        return ctx
    
    def save_task_context(self, filename, editor):
        "Update the record for this context file" 
        if DEBUG: print "SAVING CONTEXT", filename, editor
        ctx = self.get_task_context(filename)
        ctx['lineno'] = editor.GetCurrentLine()
        ctx['closed'] = not wx.GetApp().closing
        ctx.save()
        # remove all previous breakpoints and persist new ones:
        self.db["breakpoint"].delete(context_file_id=ctx['context_file_id'])
        for bp in editor.GetBreakpoints().values():
            if DEBUG: print "saving breakpoint", filename, bp
            bp = self.db["breakpoint"].new(**bp)
            bp['context_file_id'] = ctx['context_file_id'] 
            bp.save()
        # remove all previous breakpoints and persist new ones:
        self.db["fold"].delete(context_file_id=ctx['context_file_id'])
        for fold in editor.GetFoldAll():
            if DEBUG: print "saving fold", filename, fold['start_lineno']
            fold = self.db["fold"].new(**fold)
            fold['context_file_id'] = ctx['context_file_id'] 
            fold.save()
        self.db.commit()
        
    def load_task_context(self, filename, editor):
        "Read and apply the record for this context file"
        if DEBUG: print "LOADING CONTEXT", filename, editor
        ctx = self.get_task_context(filename)
        if DEBUG: print "GoTO", filename, ctx['lineno']
        editor.GotoLineOffset(ctx['lineno'], 1)
        ctx['closed'] = False
        # load all previous breakpoints and restore them:
        q = dict(context_file_id=ctx['context_file_id'])
        for bp in self.db["breakpoint"].select(**q):
            del bp['context_file_id']
            del bp['breakpoint_id']
            editor.ToggleBreakpoint(**bp)
        # load all previous folds and restore them:
        editor.FoldAll(expanding=False)
        for fold in self.db["fold"].select(**q):
            if fold['expanded']:
                if DEBUG: print "restoring fold", filename, fold['start_lineno']
                editor.SetFold(**fold)

    def tick_task_context(self):
        "Update task context file timings"
        if self.active_child and not self.task_suspended:
            #lineno = self.active_child.GetCurrentLine()
            filename = self.active_child.GetFilename()
            ctx = self.get_task_context(filename)
            if DEBUG: print "TICKING", filename, ctx, ctx['total_time']
            ctx['total_time'] = (ctx['total_time'] or 0) + 1
        # it will be saved on task deactivation (to avoid excesive db access)
    
    def get_task_context_file_relevance(self, filename):
        "Ponderate if a given context file is relevant to the current task"
        total_time_sum = sum([ctx['total_time'] or 0.0
                              for ctx in self.task_context_files.values()], 0.0)
        # check if it is a context file (do not track if never was activated)
        if filename in self.task_context_files and total_time_sum:
            ctx = self.task_context_files[filename]
            relevance = (ctx['total_time'] or 0.0) / total_time_sum  * 100
            if DEBUG: print "Relevance", filename, relevance, total_time_sum
        else:
            relevance = 0
        return relevance
        

class TaskPanel(ScrolledPanel):
    def __init__(self, parent ):

        ScrolledPanel.__init__(self, parent, -1)

        grid1 = wx.FlexGridSizer( 0, 2, 5, 5 )
        grid1.AddGrowableCol(1)
        grid1.AddGrowableRow(2)

        self.image = wx.StaticBitmap(self, size=(32, 32))
        self.label = wx.StaticText(self, -1, "Task Nº\ndate\nowner\nstatus")
        grid1.Add(self.image, 0, wx.ALIGN_CENTER_VERTICAL|
                                 wx.ALIGN_CENTER_HORIZONTAL, 5)
        grid1.Add(self.label, 1, wx.ALL | wx.EXPAND, 5)

        label = wx.StaticText(self, -1, "Title:")
        grid1.Add(label, 0, wx.ALL | wx.ALIGN_LEFT, 5)
        self.title = wx.TextCtrl(self, -1, "", size=(200, -1), )
        grid1.Add(self.title, 1, wx.LEFT | wx.RIGHT | wx.EXPAND, 5)

        label = wx.StaticText(self, -1, "Description:")
        grid1.Add(label, 0, wx.ALL | wx.ALIGN_LEFT, 5)
        self.description = wx.TextCtrl(self, -1, "", size=(200, 100), 
                                       style=wx.TE_MULTILINE)
        grid1.Add(self.description, 1, wx.LEFT | wx.RIGHT | wx.EXPAND, 5)

        self.types = sorted(connector.TAG_MAP['type'])
        self.resols = ["", ] + list(sorted(connector.TAG_MAP['resulution']))
        
        label = wx.StaticText(self, -1, "Type:")
        grid1.Add(label, 0, wx.ALL | wx.ALIGN_LEFT, 5)
        self.task_type = wx.Choice(self, -1, choices=self.types, size=(80,-1))
        grid1.Add(self.task_type, 1, wx.LEFT | wx.RIGHT | wx.EXPAND, 5)

        label = wx.StaticText(self, -1, "Resolution:")
        grid1.Add(label, 0, wx.ALL | wx.ALIGN_LEFT, 5)
        self.resolution = wx.Choice(self, -1, choices=self.resols, size=(80,-1))
        grid1.Add(self.resolution, 1, wx.LEFT | wx.RIGHT | wx.EXPAND, 5)

        btn = wx.Button(self, wx.ID_OK, label="Submit")
        btn.SetDefault()
        self.Bind(wx.EVT_BUTTON, self.OnSubmit, btn)
        grid1.Add((0, 0), 0, wx.ALL | wx.ALIGN_RIGHT, 5)
        grid1.Add(btn, 0, wx.ALL | wx.ALIGN_CENTER, 5)

        self.SetSizer(grid1)
        grid1.Fit(self)
        self.SetAutoLayout(1)
        self.SetupScrolling()
        
    def SetValue(self, item):
        self.label.SetLabel("%s\nCreated: %s\nOwner: %s\nStatus: %s" % (
                             str(item.get("name", "")),
                             item.get("started"), item.get("owner"),
                             item.get("status"), ))
        self.title.SetValue(item.get("title", ""))
        self.description.SetValue(item.get("description", ""))
        if item['type']:
            self.task_type.SetSelection(self.types.index(item['type']))
        if item['resolution']:
            self.resolution.SetSelection(self.resols.index(item['resolution']))
        
    def GetValue(self):
        item = {"title": self.title.GetValue(), 
                "description": self.description.GetValue(), 
                "type": self.types[self.task_type.GetCurrentSelection()], 
                "resolution": self.resols[self.resolution.GetCurrentSelection()],
                }
        return item

    def Load(self, connector, data, force=False):
        self.connector = connector
        # do not request GitHub data to speed up startup time
        self.data = connector.get_task(data) if force else data
        self.SetValue(self.data)
        self.image.SetBitmap(images.github_mark_32px.GetBitmap())

    def Save(self):
        self.data.update(self.GetValue())

    def OnSubmit(self, event):
        self.Save()
        self.connector.update_task(self.data)


if __name__ == "__main__":
    app = wx.App()
        
    frame = wx.Frame(None)
    panel = TaskPanel(frame)
    frame.Show()

    # load issue:
    import ConfigParser
    config = ConfigParser.ConfigParser()
    config.read('ide2py.ini')
    kwargs = dict(config.items("GITHUB"))
    kwargs['organization'] = 'reingart'
    kwargs['project'] = 'prueba'
    gh = connector.GitHub(**kwargs)
    
    panel.Load(gh, {"name": '1'})
    
    app.MainLoop()
    

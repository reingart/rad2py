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

import images

TASK_EVENT_LOG_FORMAT = "%(timestamp)s %(uuid)s %(event)s %(comment)s"

ID_CREATE, ID_ACTIVATE, ID_DELETE, ID_TASK_LABEL, ID_CONTEXT = \
    [wx.NewId() for i in range(5)]

WX_VERSION = tuple([int(v) for v in wx.version().split()[0].split(".")])


class TaskMixin(object):
    "ide2py extension for integrated task-focused interface support"
    
    def __init__(self):
        
        cfg = wx.GetApp().get_config("PSP")
        
        # create the structure for the task-based database:
        self.db = wx.GetApp().get_db()
        self.db.create("task", task_id=int, task_name=str, task_uuid=str)    

        self.db.create("context_file", context_file_id=int, task_id=int, 
                                       filename=str, lineno=int, total_time=int,
                                       closed=bool)
        self.db.create("breakpoint", breakpoint_id=int, context_file_id=int, 
                                     lineno=int, temp=bool, cond=str)
        self.db.create("fold", task_id=int, context_file_id=int, 
                               lineno=int, temporary=bool, cond=str)
                                      
        ##task_history = cfg.get("history", "task_history.dat")
        ##task_context = cfg.get("context", "task_context.dat")

        tb4 = self.CreateTaskToolbar()
        self._mgr.AddPane(tb4, aui.AuiPaneInfo().
                          Name("task_toolbar").Caption("Task Toolbar").
                          ToolbarPane().Top().Position(3).CloseButton(True))

        self._mgr.Update()

        self.AppendWindowMenuItem('Task',
            ('task_list', 'task_detail', 'task_toolbar', ), self.OnWindowMenu)
        
        task_id = cfg.get("task_id")
        if task_id:
            self.activate_task(None, task_id)

        self.CreateTaskMenu()

    def CreateTaskMenu(self):
        # create the menu items
        task_menu = self.menu['task'] = wx.Menu()
        task_menu.Append(ID_CREATE, "Create Task")
        task_menu.Append(ID_ACTIVATE, "Activate Task")
        task_menu.Append(ID_DELETE, "Delete Task")
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
        tb4.AddSimpleTool(ID_ACTIVATE, "Task", images.month.GetBitmap(),
                         short_help_string="Change current Task")
        tb4.AddLabel(ID_TASK_LABEL, "create a task...", width=100)

        tb4.Realize()
        self.task_toolbar = tb4
        return tb4
            
    def __del__(self):
        self.psp_event_log_file.close()
        self.task_list.close()

    def task_log_event(self, event, uuid="-", comment=""):
        phase = self.GetPSPPhase()
        timestamp = str(datetime.datetime.now())
        msg = PSP_EVENT_LOG_FORMAT % {'timestamp': timestamp, 'phase': phase, 
            'event': event, 'comment': comment, 'uuid': uuid}
        print msg
        self.task_event_log_file.write("%s\r\n" % msg)
        self.task_event_log_file.flush()

    def OnActivateTask(self, event):
        "List available projects, change to selected one and load/save context"
        tasks = self.get_tasks()
        dlg = wx.SingleChoiceDialog(self, 'Select a project', 'PSP Project',
                                    projects, wx.CHOICEDLG_STYLE)
        if dlg.ShowModal() == wx.ID_OK:
            self.psp_save_project()
            project_name = dlg.GetStringSelection()
            self.psp_load_project(project_name)
        dlg.Destroy()

    def activate_task(self, task_name=None, task_id=None):
        "Set task name in toolbar and uuid in config file"
        if task_id:
            # get the task for a given id
            task = self.db["task"][task_id]
        else:
            # search the task using the given name
            task = self.db["task"](task_name=task_name)
            if not task:
                # add the new task
                task = self.db["task"].new(task_name=task_name, 
                                           task_uuid=str(uuid.uuid1()))
                task.save()
        self.task_id = task['task_id']
        print "TASK ID", self.task_id, task.data_in
        self.task_toolbar.SetToolLabel(ID_TASK_LABEL, task_name)
        self.task_toolbar.Refresh()
        # store project name in config file
        wx.GetApp().config.set('TASK', 'task_id', task_id)
        wx.GetApp().write_config()

    def get_task_context(self, filename):
        "Fetch the current record for this context file (or create a new one)"
        ctx = self.db["context_file"](task_id=self.task_id, filename=filename)
        if not ctx:
            # insert the new context file to this task
            ctx = self.db["context_file"].new(task_id=self.task_id, 
                                              filename=filename)
        return ctx
    
    def save_task_context(self, filename, editor):
        "Update the record for this context file" 
        print "SAVING CONTEXT", filename, editor
        ctx = self.get_task_context(filename)
        ctx['lineno'] = editor.GetCurrentLine()
        ctx['closed'] = True
        ctx.save()
        # remove all previous breakpoints and add persist ones:
        self.db["breakpoint"].delete(context_file_id=ctx['context_file_id'])
        for bp in editor.GetBreakpoints().values():
            print "saving breakpoint", filename, bp
            bp = self.db["breakpoint"].new(**bp)
            bp['context_file_id'] = ctx['context_file_id'] 
            bp.save()
            
        
    def load_task_context(self, filename, editor):
        "Read and apply the record for this context file"
        print "LOADING CONTEXT", filename, editor
        ctx = self.get_task_context(filename)
        print "GoTO", filename, ctx['lineno']
        editor.GotoLineOffset(ctx['lineno'], 1)
        ctx['closed'] = False
        # load all previous breakpoints and restore them:
        q = dict(context_file_id=ctx['context_file_id'])
        for bp in self.db["breakpoint"].select(**q):
            del bp['context_file_id']
            del bp['breakpoint_id']
            editor.ToggleBreakpoint(**bp)


if __name__ == "__main__":
    app = wx.App()
    app.MainLoop()


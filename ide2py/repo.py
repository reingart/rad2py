#!/usr/bin/env python
# coding:utf-8

"Integrated repository support"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"


import fnmatch
import os
import sys
import wx
import wx.lib.agw.aui as aui

from repo_hg import MercurialRepo

# Define notification event for repository refresh
EVT_REPO_ID = wx.NewId()


class RepoEvent(wx.PyEvent):
    "Simple event to carry repository notification"
    def __init__(self, filename, action, status):
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_REPO_ID)
        self.data = filename, action, status


class RepoMixin(object):
    "ide2py extension for integrated repository support"
    
    def __init__(self):
        cfg = wx.GetApp().get_config("REPOSITORY")
        path = cfg.get("path", "")
        self.username = cfg.get("username", "")

        # search "open file" menu item to insert "open repository" one
        for pos, it in enumerate(self.menu['file'].GetMenuItems()):
            if it.GetId() == wx.ID_OPEN:
                break
        self.ID_OPEN_REPO = wx.NewId()
        self.menu['file'].Insert(pos+1, self.ID_OPEN_REPO, "Open Repo")
        self.Bind(wx.EVT_MENU, self.OnOpenRepo, id=self.ID_OPEN_REPO)
            
        self.repo = None #MercurialRepo(path, self.username)
        repo_panel = self.CreateRepoTreeCtrl()
        self._mgr.AddPane(repo_panel, aui.AuiPaneInfo().
                          Name("repo").Caption("Mercurial Repository").
                          Left().Layer(1).Position(1).CloseButton(True).MaximizeButton(True))
        self._mgr.Update()

        self.repo_tree.Bind(wx.EVT_LEFT_DCLICK, self.OnRepoLeftDClick)
        self.repo_tree.Bind(wx.EVT_CONTEXT_MENU, self.OnRepoContextMenu)

        self.Connect(-1, -1, EVT_REPO_ID, self.OnRepoEvent)

        # create pop-up menu
        self.CreateRepoMenu()


    def CreateRepoMenu(self):

        m = self.repo_menu = wx.Menu()
        menus = ['Diff', 'Commit', 'Pull', 'Update', 'Push', 'Add', 'Revert', 'Remove', 'Rollback']
        methods = [
            self.OnRepoDiff, self.OnRepoCommit, 
            self.OnRepoPush, self.OnRepoUpdate, self.OnRepoPull,
            self.OnRepoAdd, self.OnRepoRevert, self.OnRepoRemove,
            self.OnRepoRollback,
            ]
        for item_name, item_method in zip(menus, methods):
            item_id = wx.NewId()
            m.Append(item_id, item_name)
            self.Bind(wx.EVT_MENU, item_method, id=item_id)


    def CreateRepoToolbar(self):
        #ID_ADD, ID_DEL, ID_COMMIT = [wx.NewId() for i in range(3)]
        tb4 = wx.ToolBar(self, -1, wx.DefaultPosition, wx.DefaultSize,
                         wx.TB_FLAT | wx.TB_NODIVIDER)
        tsize = wx.Size(16, 16)
        tb4.SetToolBitmapSize(tsize)

        GetBmp = wx.ArtProvider.GetBitmap

        tb4.AddSimpleTool(
            wx.ID_UNDO, GetBmp(wx.ART_GO_UP, wx.ART_TOOLBAR, tsize), "Commit")
        tb4.AddSimpleTool(
            wx.ID_UNDO, GetBmp(wx.ART_GO_DOWN, wx.ART_TOOLBAR, tsize), "Update")

        tb4.AddSimpleTool(
            wx.ID_UNDO, GetBmp(wx.ART_HELP_SIDE_PANEL, wx.ART_TOOLBAR, tsize), "Diff")
        
        tb4.Realize()
        return tb4

    def CreateRepoTreeCtrl(self):
        panel = wx.Panel(self)
        self.repo_tree = tree = wx.TreeCtrl(panel, -1, wx.Point(0, 0), wx.Size(160, 250),
                           wx.TR_DEFAULT_STYLE | wx.NO_BORDER)
        
        imglist = wx.ImageList(16, 16, True, 2)
        imglist.Add(wx.ArtProvider_GetBitmap(wx.ART_FOLDER, wx.ART_OTHER, wx.Size(16,16)))
        imglist.Add(wx.ArtProvider_GetBitmap(wx.ART_NORMAL_FILE, wx.ART_OTHER, wx.Size(16,16)))
        imglist.Add(wx.ArtProvider_GetBitmap(wx.ART_ADD_BOOKMARK, wx.ART_OTHER, wx.Size(16,16)))
        imglist.Add(wx.ArtProvider_GetBitmap(wx.ART_DEL_BOOKMARK, wx.ART_OTHER, wx.Size(16,16)))
        imglist.Add(wx.ArtProvider_GetBitmap(wx.ART_TICK_MARK, wx.ART_OTHER, wx.Size(16,16)))
        imglist.Add(wx.ArtProvider_GetBitmap(wx.ART_CROSS_MARK, wx.ART_OTHER, wx.Size(16,16)))
        imglist.Add(wx.ArtProvider_GetBitmap(wx.ART_ERROR, wx.ART_OTHER, wx.Size(16,16)))
        imglist.Add(wx.ArtProvider_GetBitmap(wx.ART_WARNING, wx.ART_OTHER, wx.Size(16,16)))
        imglist.Add(wx.ArtProvider_GetBitmap(wx.ART_QUESTION, wx.ART_OTHER, wx.Size(16,16)))
        tree.AssignImageList(imglist)

        self.repo_filter = wx.SearchCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.repo_filter.Bind(wx.EVT_TEXT_ENTER, self.OnSearchRepo)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.repo_tree, 1, wx.EXPAND)
        sizer.Add(self.repo_filter, 0, wx.EXPAND|wx.ALL, 5)
        if 'wxMac' in wx.PlatformInfo:
            sizer.Add((5,5))  # Make sure there is room for the focus ring
        panel.SetSizer(sizer)
        return panel

    def PopulateRepoTree(self, path):
        self.repo_path = path
        self.CleanRepoTree()
        self.RefreshRepo()
        self.repo_tree.Expand(self.repo_dict[None])
        
    def CleanRepoTree(self):
        if not self.repo:
            return
            
        tree = self.repo_tree
        tree.DeleteAllItems()
        root = tree.AddRoot(self.repo_path)
        # tree model: dict of dict, keys are filenames or None for root node
        self.repo_dict = {None: root}
        
    def OnOpenRepo(self, event):
        dlg = wx.DirDialog(self, "Choose a directory:",
                          style=wx.DD_DEFAULT_STYLE
                           #| wx.DD_DIR_MUST_EXIST
                           #| wx.DD_CHANGE_DIR
                           )
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            self.path = path
            self.repo = MercurialRepo(path, self.username)
            self.PopulateRepoTree(path)
        dlg.Destroy()

    def OnSearchRepo(self, event=None):
        self.CleanRepoTree()
        self.RefreshRepo()

    def RefreshRepo(self, filename=None):
        # exit if not repository loaded:
        if not self.repo:
            return
        
        wx.BeginBusyCursor()
        
        search=self.repo_filter.GetValue()
        tree = self.repo_tree
        # icon status mapping
        icons = {'modified': 5, 'added': 2, 'deleted': 3, 'clean': 4,
                 'missing': 7, 'unknown': 8, 'ignored': 6}
        items = self.repo_dict
        
        # walk through the files, create tree nodes when needed
        for fn, st in sorted(self.repo.status(filename)):
            if st in ('ignored',):
                continue
            if search and not fnmatch.fnmatch(fn, search):
                continue
            current = items
            folders = os.path.dirname(fn).split(os.path.sep)
            basename = os.path.basename(fn)
            # split pathname, create intermediate directory nodes (if any)
            if folders[0]:
                for folder in folders:
                    if not folder in current:
                        node = tree.AppendItem(current[None], folder, 0)
                        current[folder] = {None: node}
                    current = current[folder] # chdir
            # create or update file node
            if not basename in current:
                node = tree.AppendItem(current[None], basename, icons[st])
                tree.SetPyData(node, os.path.join(self.path, fn))
                current[basename] = node
                if search:
                    tree.EnsureVisible(node)
            else:
                node = current[basename]
                tree.SetItemImage(node, icons[st], wx.TreeItemIcon_Normal)

        wx.EndBusyCursor()

    def get_selected_filename(self, event):
        item = self.repo_tree.GetSelection() 
        if item:
            filename = self.repo_tree.GetPyData(item)
            return filename


    def OnRepoLeftDClick(self, event):
        filename = self.get_selected_filename(event)
        if filename:
            self.DoOpen(filename)
        event.Skip()

    def OnRepoEvent(self, event=None):
        if event:
            filename, action, status = event.data
            print "OnRepoEvent", filename, action
            self.RefreshRepo([filename])

    def OnRepoContextMenu(self, event):
        self.PopupMenu(self.repo_menu)
        #menu.Destroy()

    def OnRepoUpdate(self, event):
        pass

    def OnRepoCommit(self, event):
        filename = self.get_selected_filename(event)
        if filename:
            dlg = wx.TextEntryDialog(
                    self, 'Commit message for %s' % filename, 'Commit', '')
            if dlg.ShowModal() == wx.ID_OK:
                message = dlg.GetValue()
                result = self.repo.commit([filename], message)
                if result is None:
                    result_msg = "No changes!"
                elif result is False:
                    result_msg = "Commit Failed!"
                else:
                    result_msg = ""
                if result_msg:
                    dlg2 = wx.MessageDialog(self, 'Commit Result',
                               result_msg, wx.OK | wx.ICON_INFORMATION)
                    dlg2.ShowModal()
                    dlg2.Destroy()
                self.RefreshRepo([filename])
            dlg.Destroy()
            
    def OnRepoDiff(self, event):
        filename = self.get_selected_filename(event)
        if filename:
            self.DoDiff(filename)

    def OnRepoAdd(self, event):
        filename = self.get_selected_filename(event)
        if filename:
            rejected = self.repo.add([filename])
            if rejected:
                dlg = wx.MessageDialog(self, ', '.join(rejected),
                           'Add file rejected', wx.OK | wx.ICON_EXCLAMATION)
                dlg.ShowModal()
                dlg.Destroy()
            self.RefreshRepo([filename])        

    def OnRepoRevert(self, event):
        dlg = wx.MessageDialog(self, 'This will restore all original files, \n'
                'Are you sure?', 'Revert to last revision',
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
        if dlg.ShowModal() == wx.ID_YES:
            self.repo.revert()
            self.RefreshRepo([])
        dlg.Destroy()

    def OnRepoRemove(self, event):
        pass

    def OnRepoPush(self, event):
        pass
    
    def OnRepoPull(self, event):
        pass

    def OnRepoRollback(self, event):
        dlg = wx.MessageDialog(self, 'Undoing the last command is dangerous, \n'
                'Are you sure?', 'Rollback last transaction',
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
        if dlg.ShowModal() == wx.ID_YES:
            self.repo.rollback()
            self.RefreshRepo([])
        dlg.Destroy()

    def DoDiff(self, filename):
        old = self.repo.cat(filename)
        new = open(filename, "U").read()
        from wxpydiff import PyDiff
        PyDiff(None, 'wxPyDiff', "repository", filename, old, new)



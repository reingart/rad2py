#!/usr/bin/env python
# coding:utf-8

"Itegrated repository support"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"


import os
import sys
import wx

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
        path = os.path.realpath("..")
        self.repo = MercurialRepo(path)
        self.CreateRepoTreeCtrl(path)
        self._mgr.AddPane(self.repo_tree, wx.aui.AuiPaneInfo().
                          Name("repo").Caption("Mercurial Repository").
                          Left().Layer(1).Position(1).CloseButton(True).MaximizeButton(True))
        self._mgr.Update()

        self.repo_tree.Bind(wx.EVT_LEFT_DCLICK, self.OnRepoLeftDClick)
        #self.repo_tree.Bind(wx.EVT_RIGHT_DOWN, self.OnRightDown)
        #self.repo_tree.Bind(wx.EVT_RIGHT_UP, self.OnRightUp)
        self.repo_tree.Bind(wx.EVT_CONTEXT_MENU, self.OnRepoContextMenu)

        self.Connect(-1, -1, EVT_REPO_ID, self.OnRepoEvent)

#        tb5 = self.CreateRepoToolbar()
#        self._mgr.AddPane(tb5, wx.aui.AuiPaneInfo().
#                          Name("tb5").Caption("Repository Toolbar").
#                          ToolbarPane().Top().Row(1).Position(4).
#                          LeftDockable(False).RightDockable(False).CloseButton(True))
#        self._mgr.Update()

        self.CreateRepoMenu()


    def CreateRepoMenu(self):

        m = self.repo_menu = wx.Menu()
        menus = ['Update', 'Commit', 'Diff', 'Revert', 'Push', 'Pull']
        methods = [self.OnRepoUpdate, self.OnRepoCommit, self.OnRepoDiff,
            self.OnRepoRevert, self.OnRepoPush, self.OnRepoPull]
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

    def CreateRepoTreeCtrl(self, path):
        self.repo_tree = tree = wx.TreeCtrl(self, -1, wx.Point(0, 0), wx.Size(160, 250),
                           wx.TR_DEFAULT_STYLE | wx.NO_BORDER)
        
        root = tree.AddRoot(path)
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
        # tree model: dict of dict, keys are filenames or None for root node
        self.repo_dict = {None: root}

        self.RefreshRepo()
        tree.Expand(root)
        return tree


    def RefreshRepo(self, filename=None):
        tree = self.repo_tree
        # icon status mapping
        icons = {'modified': 5, 'added': 2, 'deleted': 3, 'clean': 4,
                 'missing': 7, 'unknown': 8, 'ignored': 6}
        items = self.repo_dict
        
        # walk through the files, create tree nodes when needed
        for fn, st in sorted(self.repo.status(filename)):
            print fn, st
            if st in ('ignored',):
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
                tree.SetPyData(node, basename)
                current[basename] = node
            else:
                node = current[basename]
                tree.SetItemImage(node, icons[st], wx.TreeItemIcon_Normal)

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
        pass

    def OnRepoDiff(self, event):
        filename = self.get_selected_filename(event)
        if filename:
            self.DoDiff(filename)

    def OnRepoRevert(self, event):
        pass
    
    def OnRepoPush(self, event):
        pass
    
    def OnRepoPull(self, event):
        pass

    def DoDiff(self, filename):
        old = self.repo.cat(filename)
        new = open(filename, "U").read()
        from wxpydiff import PyDiff
        PyDiff(None, 'wxPyDiff', "repository", filename, old, new)


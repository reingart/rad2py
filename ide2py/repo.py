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
        self.Connect(-1, -1, EVT_REPO_ID, self.OnRepoEvent)

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


    def OnRepoLeftDClick(self, event):
        pt = event.GetPosition();
        item, flags = self.repo_tree.HitTest(pt)
        if item:
            filename = self.repo_tree.GetPyData(item)
            print filename
            self.DoOpen(filename)
        event.Skip()

    def OnRepoEvent(self, event=None):
        if event:
            filename, action, status = event.data
            print "OnRepoEvent", filename, action
            self.RefreshRepo([filename])



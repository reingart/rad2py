﻿#!/usr/bin/env python
# coding:utf-8

"Integrated repository support"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"


import cStringIO
import fnmatch
import os
import sys
import wx
import wx.lib.agw.aui as aui
import tempfile
from urlparse import urlparse

try:
    from repo_hg import MercurialRepo
except ImportError:
    MercurialRepo = None
from repo_w2p import Web2pyRepo
import fileutil
import images

# Define notification event for repository refresh
EVT_REPO_ID = wx.NewId()

# ID for base file in recent repository history
ID_FILE_REPO = [wx.NewId() for x in range(10)]


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
        self.repo_path = None

        # keep track of remote opened files
        self.remote_files_map = {}

        # search "open file" menu item to insert "open repository" one
        for pos, it in enumerate(self.menu['file'].GetMenuItems()):
            if it.GetId() == wx.ID_OPEN:
                break
        self.ID_OPEN_REPO = wx.NewId()
        self.ID_OPEN_WEB_REPO = wx.NewId()
        self.menu['file'].Insert(pos+1, self.ID_OPEN_REPO, "Open Repo\tCtrl-Shift-O")
        self.Bind(wx.EVT_MENU, self.OnOpenRepo, id=self.ID_OPEN_REPO)
        self.menu['file'].Insert(pos+2, self.ID_OPEN_WEB_REPO, "Open Web Repo\tCtrl-Shift-Alt-O")
        self.Bind(wx.EVT_MENU, self.OnOpenWebRepo, id=self.ID_OPEN_WEB_REPO)

        # search "recent files" menu item to insert "recent repos" one
        for pos, it in enumerate(self.menu['file'].GetMenuItems()):
            if it.GetId() == wx.ID_FILE:
                break
        # and a file history
        recent_repos_submenu = wx.Menu()
        self.repo_filehistory = wx.FileHistory(idBase=ID_FILE_REPO[0])
        self.repo_filehistory.UseMenu(recent_repos_submenu)
        self.menu['file'].InsertMenu(pos+1, -1, "Recent &Repos", recent_repos_submenu)
        self.Bind(wx.EVT_MENU_RANGE, self.OnRepoFileHistory, 
            id=ID_FILE_REPO[0], id2=ID_FILE_REPO[9])
           
        self.repo = None #MercurialRepo(path, self.username)
        repo_panel = self.CreateRepoTreeCtrl()
        self._mgr.AddPane(repo_panel, aui.AuiPaneInfo().
                          Name("repo").Caption("Repository").
                          Left().Layer(1).Position(1).CloseButton(True).MaximizeButton(True))
        self._mgr.Update()

        self.AppendWindowMenuItem('Repository', ('repo', ), self.OnWindowMenu)

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
        imglist.Add(images.folder.GetBitmap())
        imglist.Add(images.file_new.GetBitmap())
        
        # create a icon for each file type / status:
        
        bmp_stat = {'modified': images.modified, 'added': images.added, 
                       'deleted': images.deleted, 'clean': images.clean,
                       'unknown': images.conflict, 
                       'missing': None, 'ignored': None}
        bmp_exts = {'txt': images.file_txt, 'xml': images.file_xml, 
                     'py': images.file_py, '': images.file_new}
        self.repo_icons = {}
        i = 2
        for f_ex, f_st in [(ex, st) for ex in bmp_exts for st in bmp_stat]:
            b_ex = bmp_exts[f_ex]
            b_st = bmp_stat[f_st]
            if b_st:
                bmp = images.merge_bitmaps(b_ex.GetBitmap(), 
                                             b_st.GetBitmap())
            else:
                bmp = b_ex.GetBitmap()
            imglist.Add(bmp)
            self.repo_icons['%s_%s' % (f_ex, f_st)] = i
            i += 1

        tree.AssignImageList(imglist)

        # extra controls to search / filter
        
        self.repo_slider = wx.Slider(panel, style=wx.SL_HORIZONTAL)
        tip = wx.ToolTip('Filter context files by relevance (active task)')
        self.repo_slider.SetToolTip(tip)
        self.repo_slider.Bind(wx.EVT_SLIDER, self.OnSearchRepo)

        self.repo_filter = wx.SearchCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.repo_filter.ShowCancelButton(True)
        self.repo_filter.Bind(wx.EVT_TEXT_ENTER, self.OnSearchRepo)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.repo_tree, 1, wx.EXPAND)
        sizer.Add(self.repo_slider, 0, wx.EXPAND|wx.ALL, 5)
        sizer.Add(self.repo_filter, 0, wx.EXPAND|wx.ALL, 5)
        if 'wxMac' in wx.PlatformInfo:
            sizer.Add((5,5))  # Make sure there is room for the focus ring
        panel.SetSizer(sizer)
        
        menu = wx.Menu()
        #item = menu.AppendRadioItem(-1, "Search Filenames")
        #self.Bind(wx.EVT_MENU, self.OnSearchRepo, item)
        #item = menu.AppendRadioItem(-1, "Search Content")
        #self.Bind(wx.EVT_MENU, self.OnSearchRepo, item)
        for st in ('modified', 'added', 'deleted', 'clean', 'unknown', 
                   'missing', 'ignored'):
            item = menu.AppendCheckItem(-1, "%s" % st, "Show %s files" % st)
            item.Check((st not in ('ignored', 'unknown')))
            self.Bind(wx.EVT_MENU, self.OnSearchRepo, item)
        self.repo_filter.SetMenu(menu)

        # restore file history config:
        cfg_history = wx.GetApp().get_config("HISTORY")
        for filenum in range(9,-1,-1):
            filename = cfg_history.get('repo_%s' % filenum, "")
            if filename:
                self.repo_filehistory.AddFileToHistory(filename)
        
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
            self.DoOpenRepo(path)
            self.repo_filehistory.AddFileToHistory(path)
        dlg.Destroy()

    def OnOpenWebRepo(self, event):
        dlg = wx.TextEntryDialog(self, 
                'Enter the URL of the web2py admin:', 
                'Open a webwpy "Repository"', 
                'http://admin:a@localhost:8000/admin/webservices/call/jsonrpc')
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetValue()
            self.DoOpenRepo(path)
            self.repo_filehistory.AddFileToHistory(path)
        dlg.Destroy()


    def DoOpenRepo(self, path, relevance_threshold=0):
        if path.startswith("http://") or path.startswith("https://"):
            self.repo = Web2pyRepo(path, self.username)
        elif MercurialRepo:
            self.repo = MercurialRepo(path, self.username)
        else:
            dlg = wx.MessageDialog(self, "Unable to load repository: %s" % path,
                        'Mercurial Support not installed', 
                       wx.OK | wx.ICON_EXCLAMATION)
            dlg.ShowModal()
            dlg.Destroy()

        # set initial fall-off relevance limit:
        self.repo_slider.SetValue(relevance_threshold)
        self.PopulateRepoTree(path)

    def OnRepoFileHistory(self, evt):
        # get the file based on the menu ID
        filenum = evt.GetId() - ID_FILE_REPO[0]
        filepath = self.repo_filehistory.GetHistoryFile(filenum)
        self.DoOpenRepo(filepath)
        # add it back to the history so it will be moved up the list
        self.repo_filehistory.AddFileToHistory(filepath)


    def OnSearchRepo(self, event=None):
        self.CleanRepoTree()
        self.RefreshRepo()

    def RefreshRepo(self, filename=None):
        # exit if not repository loaded:
        if not self.repo:
            return
        
        wx.BeginBusyCursor()
        
        # get search filters
        search = "*%s*" % self.repo_filter.GetValue()
        filter_status = []
        for item in self.repo_filter.GetMenu().GetMenuItems():
            if item.IsChecked():
                filter_status.append(item.Text)
        relevance_threshold = self.repo_slider.GetValue()

        tree = self.repo_tree
        items = self.repo_dict
        
        # walk through the files, create tree nodes when needed
        for fn, st in sorted(self.repo.status(filename)):
            if st not in filter_status:
                continue
            if search and not fnmatch.fnmatch(fn, search):
                continue
            # check if this context file is relevant for the task
            if self.task_id:
                abs_fn = os.path.join(self.repo_path, fn)
                relevance = self.get_task_context_file_relevance(abs_fn)
                # filter out non-relevant context files 
                if relevance_threshold and relevance < relevance_threshold:
                    continue
            else:
                relevance = None        # not tracking, do not change color
                
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
            ext = os.path.splitext(fn)[1]
            if ext and ext.startswith("."):
                ext = ext[1:]
            if ext in ('pyw', ):
                ext = 'py'
            elif ext in ('xml', 'html', 'xhtml'):
                ext = 'xml'
            elif ext not in ('py', 'txt', 'html', 'xml'):
                ext = ""
            icon = self.repo_icons.get('%s_%s' % (ext, st))
            if not icon:
                icon = 1
            if not basename in current:
                node = tree.AppendItem(current[None], basename, icon)
                tree.SetPyData(node, os.path.join(self.repo_path, fn))
                current[basename] = node
                if search:
                    tree.EnsureVisible(node)
                # change the text color by relevance (remark the more important)
                if relevance is not None:
                    gray = (100 - relevance) / 100 * 211
                    colour = wx.Colour(gray, gray, gray)
                    tree.SetItemTextColour(node, colour)
                    # TODO: calculate the remark limit based on file count?
                    if relevance > 33:
                        tree.SetItemBold(node, True)
            else:
                node = current[basename]
                tree.SetItemImage(node, icon, wx.TreeItemIcon_Normal)

        wx.EndBusyCursor()

    def get_selected_filename(self, event):
        item = self.repo_tree.GetSelection() 
        if item:
            filename = self.repo_tree.GetPyData(item)
            return filename


    def OnRepoLeftDClick(self, event):
        filename = self.get_selected_filename(event)
        self.DoRepoOpenFile(filename)
        event.Skip()

    def DoRepoOpenFile(self, filename):
        if filename.startswith("http://") or filename.startswith("https://"):
            # remote repo, create a local temp file:
            f = tempfile.NamedTemporaryFile(delete=False)
            tmpfilename = f.name
            # fetch the file text and save to the temp file
            f.write(self.repo.cat(filename))
            f.close()
            # map the remote name to the local name:
            self.remote_files_map[tmpfilename] = filename
            # extract basename and open the window
            o = urlparse(filename)
            basename = os.path.basename(o.path)
            self.DoOpen(tmpfilename, basename)
        elif filename:
            self.DoOpen(filename)

    def OnRepoEvent(self, event=None):
        if event:
            filename, action, status = event.data
            print "OnRepoEvent", filename, action
            self.RefreshRepo([filename])

            # check if it is a remote (temp) file :
            if filename in self.remote_files_map:
                # read the temporary file
                f = open(filename, "rb")
                data = f.read()
                f.close()
                # send to the remote server
                print "WRITING", self.remote_files_map[filename]
                self.repo.put(self.remote_files_map[filename], data)
            
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
        # open files (use in-memmory file-like buffer for working base)
        file_old = cStringIO.StringIO(self.repo.cat(filename))
        file_new = open(filename, "U")
        
        # read files returning proper unicode text and other flags
        old_text, old_encoding, old_bom, old_eol, old_nl = \
            fileutil.unicode_file_read(file_old, encoding=None)
        
        new_text, new_encoding, new_bom, new_eol, new_nl = \
            fileutil.unicode_file_read(file_new, encoding=None)
        
        # normalize newlines (eol changes not supported by wxPyDiff/SM by now)
        nl = '\r\n'
        if old_nl != nl:
            old_text = old_text.replace(old_nl, nl)
        if new_nl != nl:
            new_text = new_text.replace(new_nl, nl)
        
        # re-encode unicode to same encoding
        old_text = old_text.encode("utf8")
        new_text = new_text.encode("utf8")
        
        # render the diff
        from wxpydiff import PyDiff
        PyDiff(None, 'wxPyDiff', "repository", filename, old_text, new_text)

    def RepoMixinCleanup(self):
        # A little extra cleanup is required for the FileHistory control
        if hasattr(self, "repo_filehistory"):
            # save recent file history in config file
            for filenum in range(0, self.repo_filehistory.Count):
                filename = self.repo_filehistory.GetHistoryFile(filenum)
                wx.GetApp().config.set('HISTORY', 'repo_%s' % filenum, filename)
            del self.repo_filehistory
            #self.recent_repos_submenu.Destroy() # warning: SEGV!


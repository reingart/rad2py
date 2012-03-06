#!/usr/bin/env python
# coding:utf-8

"WxPython class and function source code browser"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"

import wx
import os.path

from threading import Thread, Lock

import images
import pyparse

EVT_PARSED_ID = wx.NewId()
EVT_EXPLORE_ID = wx.NewId()
    

class ExplorerEvent(wx.PyEvent):
    """Simple event to carry arbitrary result data."""
    def __init__(self, event_type, data=None):
        wx.PyEvent.__init__(self)
        self.SetEventType(event_type)
        self.data = data

mutex = Lock()

class Explorer(Thread):
    "Worker thread to analyze a python source file"

    def __init__(self, parent, modulename, modulepath, filename):
        Thread.__init__(self)
        self.parent = parent
        self.modulename = modulename
        self.modulepath = modulepath
        self.filename = filename
        self.start()                # creathe the new thread

    def run(self):
        with mutex:
            nodes = pyparse.parseFile(self.filename)
            event = ExplorerEvent(EVT_PARSED_ID, 
                                  (self.modulename, self.filename, nodes))
            wx.PostEvent(self.parent, event)


class ExplorerTreeCtrl(wx.TreeCtrl):

    def __init__(self, parent, id, pos, size, style):
        wx.TreeCtrl.__init__(self, parent, id, pos, size, style)

    def OnCompareItems(self, item1, item2):
        # sort by pydata (lineno)
        t1 = self.GetItemPyData(item1)
        t2 = self.GetItemPyData(item2)
        if t1 < t2: return -1
        if t1 == t2: return 0
        return 1


class ExplorerPanel(wx.Panel):
    def __init__(self, parent):
        # Use the WANTS_CHARS style so the panel doesn't eat the Return key.
        wx.Panel.__init__(self, parent, -1, style=wx.WANTS_CHARS)
        self.Bind(wx.EVT_SIZE, self.OnSize)

        self.parent = parent
        self.modules = {}
        self.symbols = {}

        tID = wx.NewId()

        self.tree = ExplorerTreeCtrl(self, tID, wx.DefaultPosition, wx.DefaultSize,
                               wx.TR_HAS_BUTTONS | wx.TR_HIDE_ROOT,
                               )

        il = wx.ImageList(16, 16)
        self.images = {
            'module': il.Add(images.module.GetBitmap()),
            'class': il.Add(images.class_.GetBitmap()),
            'function': il.Add(images.function.GetBitmap()),
            'method': il.Add(images.method.GetBitmap()),
            'variable': il.Add(images.variable  .GetBitmap()),
            }
    
        self.tree.SetImageList(il)
        self.il = il
        self.Bind(wx.EVT_TREE_ITEM_EXPANDED, self.OnItemExpanded, self.tree)
        self.tree.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDClick)
        self.root = self.tree.AddRoot("")
        self.tree.SetPyData(self.root, None)

        self.Connect(-1, -1, EVT_PARSED_ID, self.OnParsed)

    def ParseFile(self, filename, refresh=False):
        modulepath, basename = os.path.split(filename)
        modulename, ext = os.path.splitext(basename)
        # if module not already in the tree, add it
        if filename not in self.modules:
            if refresh:
                # do not rebuild if user didn't "explored" it previously
                return
            module = self.tree.AppendItem(self.root, modulename)
            self.modules[filename] = module
            self.tree.SetPyData(module, (filename, 1))
            self.tree.SetItemImage(module, self.images['module'])
        else:
            module = self.modules[filename]
            self.tree.CollapseAndReset(module)
        self.tree.SetItemText(module, "%s (loading...)" % modulename)
        # Start worker thread
        thread = Explorer(self, modulename, modulepath, filename)

    def RemoveFile(self, filename):
        if filename in self.modules:
            self.tree.Delete(self.modules[filename])        
    
    def OnParsed(self, evt):
        modulename, filename, nodes = evt.data
        module = self.modules[filename]
        self.tree.SetItemText(module, modulename)
        self.tree.SelectItem(module)
        classes = {}

        imports = nodes.get_imports(1)
        for i, v in enumerate(imports):
            import_line, lineno = v
            self.AddSymbol(filename, import_line, 'module', None, lineno, module)
        #process locals
        self.AddLocals(filename, nodes, nodes, module)
        # process functions
        for f in nodes.find('function').values:
            child = self.AddSymbol(filename, f.name, 'function', f.info, f.lineno, module)
            self.AddLocals(filename, nodes, f, child)
        #process classes
        for c in nodes.find('class').values:
            child = self.AddSymbol(filename, c.name, 'class', None, c.lineno, module)
            self.AddLocals(filename, nodes, c, child)
            for o in c.values:
                if o.type == 'class' or o.type == 'function':
                    meth = self.AddSymbol(filename, o.name, 'method', o.info, o.lineno, child)
                    self.AddLocals(filename, nodes, o, meth)

        self.tree.SortChildren(module)    
        self.tree.Expand(module)
        self.working = False

    def AddSymbol(self, filename, symbol_name, symbol_type, symbol_info, 
                        lineno, parent):
        if symbol_info:
            signature = symbol_info
        else:
            signature = symbol_name
        child = self.tree.AppendItem(parent, signature)
        symbol_dict = self.symbols.setdefault(symbol_name, {})
        symbol_dict.setdefault(filename, {})[symbol_type] = lineno
        self.tree.SetItemImage(child, self.images[symbol_type])
        self.tree.SetPyData(child, (filename, lineno))
        return child

    def AddLocals(self, filename, root, node, parent):
        s = []
        names = []
        for i in range(len(node.locals)):
            name = node.locals[i]
            t, v, lineno = node.local_types[i]
            if t not in ('class', 'function', 'import'):
                info = name + ': ' + 'unknow'
                if t == 'reference':
                    if v:
                        if node.type == 'class':
                            result = root.guess_type(lineno, 'self.' + name)
                        else:
                            result = root.guess_type(lineno, name)
                        if result:
                            
                            if result[0] not in ('reference', 'class', 'function', 'import'):
                                info = name + ': ' + result[0]
                            else:
                                if result[1]:
                                    if result[0] in ('class', 'function'):
                                        info = name + ': ' + result[1].info
                                    else:
                                        info = name + ': ' + result[1]
                                else:
                                    info = name + ': ' + result[0]
                        else:
                            info = name + ': ' + v
                elif t is not None:
                    info = name + ': ' + t
                s.append((name, info, lineno))
                
        for (name, info, lineno) in s:
            self.AddSymbol(filename, info, 'variable', info, lineno, parent)

        
    def FindSymbolDef(self, filename, word):
        # search all available symbols for the given word
        symbols = self.symbols.get(word, {})
        if not symbols:
            wx.Bell()   # no match!
            return None, None
        elif len(symbols) ==1 and len(symbols.values()[0]) == 1:  # single?
            return symbols.keys()[0], symbols.values()[0].values()[0]
        else:
            # multiple symbols, choose one:
            choices = []
            for filename, symbol in symbols.items():
                for symbol_type, lineno in symbol.items():
                    choices.append(((filename, lineno), 
                                    '%s:%s (%s)' % (filename, lineno, symbol_type)))
            dlg = wx.SingleChoiceDialog(self.parent, 'Pick a symbol', 
                                        'Find Symbol', 
                                        [choice[1] for choice in choices])
            dlg.ShowModal()
            choice = choices[dlg.GetSelection()][0]
            dlg.Destroy()
            return choice

    def OnItemExpanded(self, event):
        item = event.GetItem()
        if item:
            self.tree.SortChildren(item)  

    def OnLeftDClick(self, event):
        pt = event.GetPosition();
        item, flags = self.tree.HitTest(pt)
        if item:
            filename, lineno = self.tree.GetItemPyData(item)
            event = ExplorerEvent(EVT_EXPLORE_ID, 
                              (filename, lineno))
            wx.PostEvent(self.parent, event)
        event.Skip()

    def OnSize(self, event):
        w,h = self.GetClientSizeTuple()
        self.tree.SetDimensions(0, 0, w, h)


class TestFrame(wx.Frame):

    def __init__(self, filename=None):
        wx.Frame.__init__(self, None)
        self.Show()
        self.panel = ExplorerPanel(self)
        self.panel.ParseFile(filename)
        #while 'main' not in self.panel.symbols:
        #    wx.Yield()
        #print self.panel.symbols
        #filename, lineno = self.panel.FindSymbolDef(filename, "main")
        #print filename, lineno
        self.SendSizeEvent() 


if __name__ == '__main__':
    
    def main():
        app = wx.App()
        frame = TestFrame(filename=os.path.abspath("pyparse.py"))
        app.MainLoop()
    
    main()

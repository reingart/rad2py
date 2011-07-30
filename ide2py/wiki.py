#!/usr/bin/env python
# coding:utf-8

"Integrated Simpler Wiki Text WYSWYG Edit Control (using web2py markmin)"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"
 
import os
import sys
import wx
import wx.lib.agw.flatnotebook as fnb
import wx.html


try:
    sys.path.append(r"/home/reingart/web2py-hg")
    from gluon.contrib.markmin.markmin2html import render
except ImportError:
    raise
    render = lambda x: x


SAMPLE_WIKI_TEXT = """
# Markmin Examples

## Bold, italic, code and links

 **bold** ''italic'' ``verbatim`` http://google.com [[click me #myanchor]]

[[title link]]

## Images

[[some image http://www.web2py.com/examples/static/web2py_logo.png right 200px]]

## Unordered Lists
- Dog
- Cat
- Mouse

Two new lines between items break the list in two lists.

## Ordered Lists
+ Dog
+ Cat
+ Mouse


## Tables

---------
**A** | **B** | **C**
0 | 0 | X
0 | X | 0
X | 0 | 0
-----:abc

### Blockquote

-----
Hello world
-----

### Code, ``<code>``, escaping and extra stuff

``
def test():
    return "this is Python code"
``:python

"""

class WikiPanel(wx.Panel):
 
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(sizer)

        bookstyle = fnb.FNB_NODRAG | fnb.FNB_SMART_TABS
        self.book = fnb.FlatNotebook(self, wx.ID_ANY, agwStyle=bookstyle)

        sizer.Add(self.book,1, wx.ALL | wx.EXPAND)

        # Add some pages to the second notebook

        self.text = wx.TextCtrl(self.book, -1, SAMPLE_WIKI_TEXT, style=wx.TE_MULTILINE)
        self.book.AddPage(self.text, "Edition")

        self.html = wx.html.HtmlWindow(self, -1, wx.DefaultPosition, wx.Size(400, 300))
        if "gtk2" in wx.PlatformInfo:
            self.html.SetStandardFonts()
        self.book.AddPage(self.html,  "Preview")
        
        sizer.Layout()
        self.SendSizeEvent()
        
        self.Bind(fnb.EVT_FLATNOTEBOOK_PAGE_CHANGING, self.OnPageChanging)
        self.Bind(fnb.EVT_FLATNOTEBOOK_PAGE_CHANGED, self.OnPageChanged)
        
        #self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)


    def OnActivate(self, event):
        pass
        
    def OnDeactivate(self, event):
        pass 
        
    def OnKeyDown(self, event):
        key = event.GetKeyCode()
        control = event.ControlDown()
        shift=event.ShiftDown()
        alt = event.AltDown()
        if key == wx.WXK_TAB and control:
            self.pass1

    def OnPageChanging(self, event):
        page = event.GetOldSelection()
        if page==0:
            # save current cursor position
            self.sel = self.text.GetSelection()
        if page==1:
            # restore previous selection (really needed?)
            self.text.SetSelection(*self.sel)
        event.Skip()

    def OnPageChanged(self, event):
        page = event.GetSelection()
        if page==0:
            wx.CallAfter(self.text.SetFocus)
        if page==1:
           self.html.SetPage(render(self.text.GetValue()))
        event.Skip()


class SimpleWiki(wx.Frame):

    def __init__(self):
        wx.Frame.__init__(self, None)

        self.panel = WikiPanel(self)
        self.Show()

if __name__ == '__main__':
    app = wx.App()
    browser = SimpleWiki()
    #browser.panel.Open(url)
    app.MainLoop()

       



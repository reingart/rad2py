#!/usr/bin/env python
# coding:utf-8

"Integration of diff tool"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"

import os
import difflib
import wx
import wx.html


def diff(from_filename, to_filename, context=True, numlines=2):
    fromdesc = os.path.basename(from_filename)
    todesc= os.path.basename(to_filename)
    fromlines = open(from_filename, 'U').readlines()
    tolines = open(to_filename, 'U').readlines()

    htmldiff = difflib.HtmlDiff(tabsize=4)
    html = htmldiff.make_file(fromlines,tolines,fromdesc,todesc)
    return html

    
class SimpleDiff(wx.Frame):

    def __init__(self, html):
        wx.Frame.__init__(self, None)
        self.ctrl = wx.html.HtmlWindow(self, -1, wx.DefaultPosition, wx.Size(400, 300))
        if "gtk2" in wx.PlatformInfo:
            self.ctrl.SetStandardFonts()
        self.ctrl.SetPage(html)
        self.Show()
        #return ctrl    
        self.SendSizeEvent() 

    
if __name__ == '__main__':

    
    html = diff("hola.py","hola.py.orig")
    print html
    open("diff.html","w").write(html)
    app = wx.App(redirect=False)
    browser = SimpleDiff(html)
    #browser.panel.Open(url)
    browser.Show()
    app.MainLoop()


    

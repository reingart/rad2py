#!/usr/bin/env python
# coding:utf-8

"Integrated Simpler Web Browser for testing web2py apps"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"
 
# Based on wxPython examples (webkit panel adapted by Marcelo Fidel Fernández)
# http://www.marcelofernandez.info & http://wiki.wxpython.org/wxGTKWebKit

 
import os
import sys
import wx

DEFAULT_URL = 'http://www.python.org'


if wx.Platform in ('__WXGTK__', '__WXMAC__'):
    import gobject
    gobject.threads_init()
    import gtk, gtk.gdk
    import webkit


    class BrowserPanel(wx.Panel):
        """wxWebkitGTK - Componente wxPython que embebe un navegador
        """

        def __init__(self, *args, **kwargs):
            wx.Panel.__init__(self, *args, **kwargs)
            # Aquí es donde se hace la "magia" de embeber webkit en wxGTK.
            whdl = self.GetHandle()
            window = gtk.gdk.window_lookup(whdl)
            # Debemos mantener la referencia a "pizza", sino obtenemos un segfault.
            self.pizza = window.get_user_data()
            # Obtengo el padre de la clase GtkPizza, un gtk.ScrolledWindow
            self.scrolled_window = self.pizza.parent
            # Saco el objeto GtkPizza para poner un WebView en su lugar
            self.scrolled_window.remove(self.pizza)
            self.webview = webkit.WebView()
            self.scrolled_window.add(self.webview)
            self.scrolled_window.show_all()

        # Podemos acceder a todos los métods del objeto WebView
        # http://webkitgtk.org/reference/webkitgtk-webkitwebview.html
        def LoadURL(self, url):
            self.webview.load_uri(url)
            

elif wx.Platform == '__WXMSW__':
    import wx.lib.iewin as iewin


    class BrowserPanel(wx.Panel):
        "Internet Explorer Browser Panel (windows)"
        def __init__(self, parent):
            wx.Panel.__init__(
                self, parent, -1,
                style=wx.TAB_TRAVERSAL|wx.CLIP_CHILDREN|wx.NO_FULL_REPAINT_ON_RESIZE
                )
            self.ie = iewin.IEHtmlWindow(self)

            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.Add(self.ie, 1, wx.EXPAND)
            # Since this is a wx.Window we have to call Layout ourselves
            self.Bind(wx.EVT_SIZE, self.OnSize)
            self.SetSizer(sizer)
            ## Hook up the event handlers for the IE window.  
            self.ie.AddEventSink(self)

        def LoadURL(self, url):
            #self.ie.LoadUrl(self.current)
            self.ie.Navigate(url)

        def OnSize(self, evt):
            self.Layout()

        def BeforeNavigate2(self, this, pDisp, URL, Flags, TargetFrameName,
                            PostData, Headers, Cancel):
            print 'BeforeNavigate2: %s\n' % URL[0]
            if URL[0] == 'http://www.microsoft.com/':
                if wx.MessageBox("Are you sure you want to visit Microsoft?",
                                 style=wx.YES_NO|wx.ICON_QUESTION) == wx.NO:
                    # This is how you can cancel loading a page. 
                    Cancel[0] = True
                    

        def NewWindow3(self, this, pDisp, Cancel, Flags, urlContext, URL):
            print 'NewWindow3: %s\n' % URL
            Cancel[0] = True   # Veto the creation of a  new window.

        #def ProgressChange(self, this, progress, progressMax):
        #    self.log.write('ProgressChange: %d of %d\n' % (progress, progressMax))
            
        def DocumentComplete(self, this, pDisp, URL):
            self.current = URL[0]


class SimpleBrowserPanel(wx.Panel):
 
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self.TxtUrl = wx.TextCtrl(self, wx.ID_ANY, style=wx.TE_PROCESS_ENTER)
        self.TxtUrl.Bind(wx.EVT_TEXT_ENTER, self.OnTxtURL)
        self.Box = wx.BoxSizer(wx.VERTICAL)
        self.Box.Add(self.TxtUrl, proportion=0, flag=wx.EXPAND)
        self.SetSizer(self.Box)
        self.SetSize((800,600))
        self.Show()
        self.browser = BrowserPanel(self)
        self.Box.Add(self.browser, proportion=1, flag=wx.EXPAND)
        self.SendSizeEvent() 
 
    def OnTxtURL(self, event):
        url = self.TxtUrl.GetValue() 
        self.browser.LoadURL(url)
        self.TxtUrl.SetValue(url)
        #self.SetTitle('wxSimpleBrowser - %s' % url)

    def LoadURL(self, url):
        self.TxtUrl.SetValue(url)
        self.browser.LoadURL(url)

class SimpleBrowser(wx.Frame):

    def __init__(self):
        wx.Frame.__init__(self, None)
        self.Show()
        self.panel = SimpleBrowserPanel(self)


if __name__ == '__main__':
    app = wx.App()
    browser = SimpleBrowser()
    #browser.panel.Open(url)
    app.MainLoop()

       



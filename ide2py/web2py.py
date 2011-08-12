#!/usr/bin/env python
# -*- coding: utf-8 -*-

"Async mono-thread web2py (development) server extension to ide2py"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"

# Just for debug by now, based on web2py widget app and stlib serve_forever
# WARNING: do not request a web2py page from main thread! (it will block!)

import os
import select
from wsgiref.simple_server import make_server, demo_app 
import sys
import wx


class Web2pyMixin(object):
    "ide2py extension to execute web2py under debugger and shell"

    def __init__(self, path="../web2py", port=8006, password="a"):
        "start-up a web2py server instance"

        # read configuration with safe defaults        
        cfg = wx.GetApp().get_config("WEB2PY")
        path = cfg.get("path", path)
        password = cfg.get("password", password)
        port = cfg.get("port", port)
        host = "127.0.0.1"
        
        if path:           
            # store current directory
            prevdir = os.path.abspath(os.curdir)
           
            try:
                os.chdir(path)
                sys.path.insert(0, path)
                from gluon.main import wsgibase, save_password

                # store admin password
                save_password(password, port)

                # create a wsgi server
                self.web2py_httpd = make_server(host, port, wsgibase)
                print "Serving HTTP on port %s..." % port

                # connect to idle event to poll and serve requests
                self.Bind(wx.EVT_IDLE, self.OnIdleServeWeb2py)

                # open internal browser at default page:
                url = "http://%s:%s/" % (host, port)
                if self.browser:
                    self.browser.LoadURL(url)
                else:
                    # no interna browser, open external one
                    try:
                        import webbrowser
                        webbrowser.open(url)
                    except:
                        print 'warning: unable to detect your browser'

            except Exception, e:
                raise
                dlg = wx.MessageDialog(self, unicode(e),
                           'cannot start web2py!', wx.OK | wx.ICON_EXCLAMATION)
                dlg.ShowModal()
                dlg.Destroy()
            finally:
                # recover original directory
                os.chdir(prevdir)

    def OnIdleServeWeb2py(self, event):
        "If there is a request pending, serve it under debugger control"
        poll_interval = 0   # return inmediatelly
        # check if socket is ready to read data (incoming request):
        r, w, e = select.select([self.web2py_httpd], [], [], poll_interval)
        if self.web2py_httpd in r and not self.debugging:
            # prevent reentry on debug critical section (TODO mutex)
            self.debugging = True
            # debug, but continue at "full-speed" (set breakpoints!)
            self.debugger.start_continue = True
            self.debugger.RunCall(self.web2py_httpd.handle_request, 
                                  interp=self.shell.interp)
            # clean running line indication
            self.GotoFileLine()
            # allow new request to be served:
            self.debugging = False

    def web2py_namespace(self):
        "build a namespace suitable for editor autocompletion and calltips"
        try:
            from gluon.globals import Request, Response, Session
            from gluon.compileapp import build_environment, DAL
            request = Request()
            response = Response()
            session = Session()
            # fake request values
            request.folder = ""
            request.application = "welcome"
            request.controller = "default"
            request.function = "index"
            ns = build_environment(request, response, session)
            # fake common model objects
            db = ns['db'] = DAL("sqlite:memory")
            from gluon.tools import Auth, Crud, Service
            ns['auth'] = Auth(db)
            ns['crud'] = Crud(db)
            ns['service'] = Service()
        except Exception, e:
            raise
            print e
            ns = {}
        return ns


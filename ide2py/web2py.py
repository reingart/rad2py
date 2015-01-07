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
from urlparse import urlparse
import sys
import traceback
import wx


if False:
    # let pyinstaller to detect web2py modules 
    #     hook-gluon.main.py is needed in pyinstaller/hooks
    #     with hiddenimports = gluon.import_all.base_modules
    #     web2py must be installed on parent folder
    import gluon.main
    
    # this libraries are required by psp2py
    import matplotlib
    import matplotlib.pyplot
    import matplotlib.colors
    import numpy
    import pylab
    
    
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
                # update current directory and python path to find web2py:
                os.chdir(path)
                sys.path.insert(0, os.path.abspath(os.curdir))
                from gluon.main import wsgibase, save_password
                from gluon.contrib import qdb

                # store admin password
                save_password(password, port)

                web2py_env = {} ##self.build_web2py_environment()

                # Start a alternate web2py in a separate thread (for blocking requests)
                from threading import Thread
                def server(host, port, password):
                    save_password(password, port)
                    qdb.init(redirect=False)
                    qdb.qdb.do_debug()

                    def wrapped_app(environ, start_response):
                        "WSGI wrapper to allow debugging"
                        # hanshake with front-end on each request (update ui)
                        # not realy needed (request processing is sequential)
                        ##qdb.qdb.startup()
                        # process the request as usual
                        return wsgibase(environ, start_response)

                    httpd2 = make_server(host, port, wrapped_app)
                    print "THREAD - Serving HTTP on port2 %s..." % port
                    httpd2.serve_forever(poll_interval=0.01)

                thread = Thread(target=server, args=(host, port, password))
                thread.daemon = True     # close on exit
                wx.CallLater(2, thread.start)

                # open internal browser at default page:
                url = "http://%s:%s/" % (host, port)
                if self.browser:
                    self.browser.LoadURL(url)
                    pass
                else:
                    # no internal browser, open external one
                    try:
                        import webbrowser
                        webbrowser.open(url)
                    except:
                        print 'warning: unable to detect your browser'
                                
            except Exception, e:
                self.ShowInfoBar(u"cannot start web2py!: %s" % unicode(e), 
                                 flags=wx.ICON_ERROR, key="web2py")
                web2py_env = {}
            finally:
                # recover original directory
                os.chdir(prevdir)
            self.web2py_environment = web2py_env
            
    def build_web2py_environment(self):
        "build a namespace suitable for editor autocompletion and calltips"
        # warning: this can alter current global variable, use with care!
        try:
            from gluon.globals import Request, Response, Session
            from gluon.compileapp import build_environment, DAL
            request = Request({})
            response = Response()
            session = Session()
            # fake request values
            request.folder = ""
            request.application = "welcome"
            request.controller = "default"
            request.function = "index"
            ns = build_environment(request, response, session, )
            # fake common model objects
            db = ns['db'] = DAL("sqlite:memory")
            from gluon.tools import Auth, Crud, Service
            ns['auth'] = Auth(db)
            ns['crud'] = Crud(db)
            ns['service'] = Service()
        except Exception, e:
            traceback.print_exc()
            ns = {}
        return ns

    def web2py_namespace(self):
        return self.web2py_environment
        



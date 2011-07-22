#!/usr/bin/env python
# -*- coding: utf-8 -*-

"Mono-thread web2py for development"

# Just for debug test by now

import os
import sys

sys.argv.extend(["-a", "a"])

path = "/home/reingart/web2py"
os.chdir(path)

sys.path.insert(0, path)

### no_threads_web2py.py ### 
from wsgiref.simple_server import make_server, demo_app 
from gluon.main import wsgibase 
httpd = make_server('', 8006, wsgibase) 
print "Serving HTTP on port 8006..." 
# Respond to requests until process is killed 

import dummy_threading as dummy_threading
import thread
thread.start_new_thread(httpd.serve_forever,())
### end file ### 

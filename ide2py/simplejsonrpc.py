#!/usr/bin/python
# -*- coding: utf-8 -*-
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by the
# Free Software Foundation; either version 3, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTIBILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.

"Pythonic simple JSON RPC Client implementation"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "LGPL 3.0"
__version__ = "0.01"


import urllib2
import sys
try:
    import gluon.contrib.simplejson as json     # try web2py json serializer 
except ImportError:
    try:
        import json                             # try stdlib (py2.6)
    except:
        import simplejson as json               # try external module

class JSONRPCError(RuntimeError):
    "Error object for remote procedure call fail"
    def __init__(self, code, message):
        self.code = code
        self.message = message
    def __unicode__(self):
        return u"%s: %s" % (self.code, self.message)
    def __str__(self):
        return self.__unicode__().encode("ascii","ignore")        


class JSONRPCClient(object):
    "JSON RPC Simple Client Service Proxy"
    def __init__(self, location=None, exceptions=True, trace=True, timeout=60):
        self.location = location        # server location (url)
        self.trace = trace              # show debug messages
        self.exceptions = exceptions    # raise errors? (JSONRPCError)
        self.timeout = timeout
        self.json_request = self.json_response = ''

    def __getattr__(self, attr):
        "pseudo method that can be called"
        return lambda *args: self.call(attr, *args)
    
    def call(self, method, *args):
        "JSON RPC communication (method invocation)"

        # build data sent to the service
        data = {'id': 1, 'method': method, 'params': args, }
        body = json.dumps(data)
        headers = {'Content-type': 'text/x-json; charset="UTF-8"',
                   'Content-length': str(len(body)),}

        # make HTTP request
        req = urllib2.Request(self.location)
        for key, value in headers.items():
            req.add_header(key, value)
        req.add_data(body)

        if self.trace:
            print "-"*80
            print "POST %s" % self.location
            print '\n'.join(["%s: %s" % (k,v) for k,v in headers.items()])
            print u"\n%s" % body

        # send request and receive result (timeout only available on py2.6):
        if sys.version_info[0:2] > (2,5):
            f = urllib2.urlopen(req, timeout=self.timeout)
        else:
            f = urllib2.urlopen(req)
        content = f.read()
        
        # store plain request and response for further debugging
        self.json_request = body
        self.json_response = content

        if self.trace: 
            print '\n', f.info(), '\n', content, '\n', "="*80

        # parse json data coming from service 
        # {'version': '1.1', 'id': id, 'result': result, 'error': None}
        response = json.loads(content)

        self.error = response['error']
        if self.error and self.exceptions:
            # {'name': 'JSONRPCError', 'code': code, 'message': message}
            raise JSONRPCError(self.error['code'], self.error['message'])
            
        return response.get('result')


if __name__ == "__main__":
    # basic tests:
    client = JSONRPCClient(
                location="http://localhost:8000/psp2py/services/call/jsonrpc",
                exceptions=True, trace=True,
                )
    print client.add(1, 2)


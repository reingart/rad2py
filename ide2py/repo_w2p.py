#!/usr/bin/env python
# coding:utf-8

"Integration of web2py remote admin"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"

import os

import simplejsonrpc


class Web2pyRepo(object):

    def __init__(self, server_url, username=""):
        self.server_url = server_url
        # connect to web2py server:
        self.w2p_rpc_client = simplejsonrpc.ServiceProxy(server_url, 
                                                         verbose=True)

    def add(self, filepaths, dry_run=False, subrepo=None):
        "add the specified files on the next commit"
        return

    def commit(self, filepaths, message):
        "commit the specified files or all outstanding changes"
        return False # fail

    def cat(self, file1, revision=None):
        "return the current or given revision of a file"
        if file1.startswith(self.server_url):
            file1 = file1[len(self.server_url)+1:]
        if file1.startswith("/"):
            file1 = file1[1:]
        return self.w2p_rpc_client.read_file(file1)

    def put(self, file1, data):
        "write the file contents"
        if file1.startswith(self.server_url):
            file1 = file1[len(self.server_url)+1:]
        if file1.startswith("/"):
            file1 = file1[1:]
        return self.w2p_rpc_client.write_file(file1, data)

    def history(self):
        raise NotImplementedError("web2py repo history is not implemented!")

    def remove(self, filepaths):
        "remove the specified files on the next commit"
        raise NotImplementedError("web2py repo remove is not implemented!")

    def revert(self, revision=None):
        raise NotImplementedError("web2py repo revert is not implemented!")

    def status(self, path=None):
        "show changed files in the working directory"

        for app in self.w2p_rpc_client.list_apps():
            #yield app, 'clean'
            for filename in self.w2p_rpc_client.list_files(app):
                yield "%s/%s" % (app, filename), 'clean'

    def rollback(self, dry_run=None):
        "Undo the last transaction (dangerous): commit, import, pull, push, ..."
        raise NotImplementedError("web2py repo rollback is not implemented!")


if __name__ == '__main__':
    import sys
    
    url = "http://admin:a@localhost:8000/admin/webservices/call/jsonrpc"
    try:
        r = Web2pyRepo(url)
        if '--status' in sys.argv:
            for st, fn in r.status():
                print st, fn
        if '--cat' in sys.argv:
            print r.cat(url+"/welcome/controllers/default.py")
        if '--commit' in sys.argv:
            ret = r.commit(["hola.py"], "test commit!")
            print "result", ret
        if '--add' in sys.argv:
            print r.add(["pyi25.py"])
    except simplejsonrpc.JSONRPCError, e:
        print "=" * 80
        print str(e)
        print "-" * 80
        print e.data
        print "-" * 80



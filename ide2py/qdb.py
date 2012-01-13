#!/usr/bin/env python
# coding:utf-8

"Queues(Pipe)-based independent remote Python Debugger"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"

# remote debugger queue-based (jsonrpc-like interface)
# based on idle, inspired by pythonwin implementation

import bdb
import os
import sys
import traceback
import json


def log(func):
    def deco_fn(*args, **kwargs):
        print "call", func.__name__
        r = func(*args, **kwargs)
        print "ret", r
        return r
    return deco_fn


class Qdb(bdb.Bdb):

    def __init__(self, pipe):
        bdb.Bdb.__init__(self)
        self.frame = None
        self.interacting = 0
        self.waiting = False
        self.pipe = pipe # for communication
        self.start_continue = True # continue on first run

    @log
    def user_line(self, frame):
        self.interaction(frame)

    @log
    def user_exception(self, frame, info):
        print info
        extype, exvalue, trace = info
        # pre-process stack trace as it isn't pickeable (cannot be sent pure)
        trace = traceback.extract_tb(trace)
        msg = {'method': 'ExceptHook', 'args':(extype, exvalue, trace)}
        self.pipe.send(msg)
        self.interaction(frame, info)

    @log
    def Run(self, code, interp=None, *args, **kwargs):
        try:
            self.interp = interp
            self.interacting = self.start_continue and 1 or 2
            return self.run(code, *args, **kwargs)
        finally:
            self.interacting = 0

    @log
    def RunCall(self, function, interp=None, *args, **kwargs):
        try:
            self.interp = interp
            self.interacting = self.start_continue and 1 or 2
            return self.runcall(function, *args, **kwargs)
        finally:
            self.interacting = 0

    @log
    def interaction(self, frame, info=None):
        # first callback (Run)?, just continue...
        if self.interacting == 1:
            self.interacting += 1
            self.set_continue()
            return
        code, lineno = frame.f_code, frame.f_lineno
        filename = code.co_filename
        basename = os.path.basename(filename)
        message = "%s:%s" % (basename, lineno)
        if code.co_name != "?":
            message = "%s: %s()" % (message, code.co_name)
        #  sync_source_line()
        if frame and filename[:1] + filename[-1:] != "<>" and os.path.exists(filename):
            # notify debugger
            self.pipe.send({'method': 'DebugEvent', 'args': (filename, lineno)})

        # wait user events 
        self.waiting = True    
        self.frame = frame
         # save and change interpreter namespaces to the current frame
        ## frame.f_locals
        # copy globals into interpreter, so them can be inspected 
        ## frame.f_globals
        try:
            while self.waiting:
                print ">>>",
                request = self.pipe.recv()
                print request
                response = {'version': '1.1', 'id': request.get('id'), 
                            'result': None, 
                            'error': None}
                try:
                    # dispatch message (JSON RPC like)
                    method = getattr(self, request['method'])
                    response['result'] = method.__call__(*request['args'], 
                                                **request.get('kwargs', {}))
                except Exception, e:
                    response['error'] = {'code': 0, 'message': str(e)}
                self.pipe.send(response)

        finally:
            self.waiting = False
        self.frame = None

    @log
    def Continue(self):
        self.set_continue()
        self.waiting = False

    @log
    def Step(self):
        self.set_step()
        self.waiting = False

    @log
    def StepReturn(self):
        self.set_return(self.frame)
        self.waiting = False

    @log
    def Next(self):
        self.set_next(self.frame)
        self.waiting = False

    @log
    def Quit(self):
        self.set_quit()
        self.waiting = False

    @log
    def Jump(self, lineno):
        arg = int(lineno)
        try:
            self.frame.f_lineno = arg
        except ValueError, e:
            print '*** Jump failed:', e
            return False

    @log
    def SetBreakpoint(self, filename, lineno, temporary=0):
        self.set_break(self.canonic(filename), lineno, temporary)

    @log
    def ClearBreakpoint(self, filename, lineno):
        self.clear_break(filename, lineno)

    @log
    def ClearFileBreakpoints(self, filename):
        self.clear_all_file_breaks(filename)

    @log
    def do_clear(self, arg):
        # required by BDB to remove temp breakpoints!
        err = self.clear_bpbynumber(arg)
        if err:
            print '*** DO_CLEAR failed', err

    @log
    def inspect(self, arg):
        try:
            return eval(arg, self.frame.f_globals,
                        self.frame.f_locals)
        except:
            t, v = sys.exc_info()[:2]
            if isinstance(t, str):
                exc_type_name = t
            else: exc_type_name = t.__name__
            return '*** %s: %s' % (exc_type_name, repr(v))

    @log
    def reset(self):
        bdb.Bdb.reset(self)
        self.waiting = False
        self.frame = None

    @log
    def post_mortem(self, t=None):
        # handling the default
        if t is None:
            # sys.exc_info() returns (type, value, traceback) if an exception is
            # being handled, otherwise it returns None
            t = sys.exc_info()[2]
            if t is None:
                raise ValueError("A valid traceback must be passed if no "
                                 "exception is being handled")

        self.reset()
        
        # get last frame:
        while t is not None:
            frame = t.tb_frame
            t = t.tb_next
            print frame, t
            print frame.f_code, frame.f_lineno

        self.interaction(frame)


class Pipe(object):
    "Simulated pipe for threads"
    
    def __init__(self, name, in_queue, out_queue):
        self.__name = name
        self.in_queue = in_queue
        self.out_queue = out_queue

    def send(self, data):
        print self.__name, "send", data
        self.out_queue.put(data, block=True)
        print self.__name, "joined"

    def recv(self, count=None, timeout=None):
        print self.__name, "recv", "..."
        data = self.in_queue.get(block=True, timeout=timeout)
        print self.__name, "recv", data
        return data
        


if __name__ == '__main__':
    def f(pipe):
        print "creating debugger"
        qdb = Qdb(pipe=pipe)
        print "set trace"

        qdb.set_trace()
        print "hello world!"
        print "good by!"
        saraza

    if 'process' in sys.argv:
        from multiprocessing import Process, Pipe
        pipe, child_conn = Pipe()
        p = Process(target=f, args=(child_conn,))
    else:
        from threading import Thread
        from Queue import Queue
        parent_queue, child_queue = Queue(), Queue()
        pipe = Pipe("parent", parent_queue, child_queue)
        child_conn = Pipe("child", child_queue, parent_queue)
        p = Thread(target=f, args=(child_conn,))
    
    p.start()
    i = 0
    while 1:
        print "<<<", pipe.recv()
        raw_input()
        msg = {'method': 'Step', 'args': (), 'id': i}
        pipe.send(msg)
        i += 1

    p.join()
    

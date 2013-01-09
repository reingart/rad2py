self = None
poll = None
quitting = False
breaks = []

def trace_dispatch(frame, str event, arg):
    # check for non-interaction rpc (set_breakpoint, interrupt)
    while poll():
        self.pull_actions()
    if (frame.f_code.co_filename, frame.f_lineno) not in breaks and \
        self.fast_continue:
        return self.trace_dispatch
    print "CYTHON", frame.f_code.co_filename, frame.f_lineno
    # process the frame (see Bdb.trace_dispatch)
    if quitting:
        return # None
    if event == 'line':
        return self.dispatch_line(frame)
    if event == 'call':
        return self.dispatch_call(frame, arg)
    if event == 'return':
        return self.dispatch_return(frame, arg)
    if event == 'exception':
        return self.dispatch_exception(frame, arg)
    
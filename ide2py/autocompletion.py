#!/usr/bin/env python
# coding:utf-8

"Smart code autocompletion & call tips using JEDI (via multiprocessing RPC)"


__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2016 Mariano Reingart"
__license__ = "GPL 3.0"


import os
import sys


# autocompletion library (imported later):
jedi = None


class AutocompletionServer(object):
    "Remote RPC API to JEDI autocompletion library "
    
    def __init__(self):
        # initiate virtual environment
        if "VIRTUAL_ENV" in os.environ:
            venv = os.environ['VIRTUAL_ENV']
            sys.path.insert(0, venv)
            activate_this = os.path.join(venv, "bin", "activate_this.py")
            execfile(activate_this, dict(__file__=activate_this))
            print("virtualenv %s" % activate_this)
        global jedi
        import jedi

    def GetScript(self, source, line, col, filename):
        "Return Jedi script object suitable to AutoComplete and ShowCallTip"
        return jedi.Script(source, line, col, filename)

    def GetCompletions(self, source, pos, col, line, filename):
        "Return suitable words for autocompletion"
        script = self.GetScript(source, line, col, filename)
        completions = script.completions()
        return [{"name": comp.name, "type": comp.type} for comp in completions]

    def GetCallTips(self, source, pos, col, line, filename):
        "Return tip (parameters) and ducumentation"
        script = self.GetScript(source, line, col, filename)
        # parameters:
        for signature in script.call_signatures():
            params = [p.get_code().replace('\n', '') for p in signature.params]
            try:
                params[signature.index] = '%s' % params[signature.index]
            except (IndexError, TypeError):
                pass
        else:
            params = []
        tip = ', '.join(params)
        # normal docstring
        definitions = script.goto_definitions()
        if definitions:
            docs = ['Docstring for %s\n%s\n%s' % (d.desc_with_module, '=' * 40, d.doc)
                if d.doc else '|No Docstring for %s|' % d for d in definitions]
            doc = ('\n' + '-' * 79 + '\n').join(docs)
        else:
            doc = ""
        return tip, doc

    def GetDefinition(self, source, pos, col, line, filename):
        #prepare
        script = self.GetScript(source, pos, col, line, filename)
        if True:
            definitions = script.goto_assignments()
        else:
            definitions = script.goto_definitions()
        while definitions:
            definition = definitions.pop()
            if "__builtin__" not in definition.module_path:
                break
        else:
            return None, None, None
        return definition.module_path, definition.line, definition.column+1


# WORKAROUND for python3 server using pickle's HIGHEST_PROTOCOL (now 3) 
# but python2 client using pickles's protocol version 2
if sys.version_info[0] > 2:

    import multiprocessing.reduction        # forking in py2

    class ForkingPickler2(multiprocessing.reduction.ForkingPickler):
        def __init__(self, file, protocol=None, fix_imports=True):
            # downgrade to protocol ver 2
            protocol = 2
            super().__init__(file, protocol, fix_imports)

    multiprocessing.reduction.ForkingPickler = ForkingPickler2


from multiprocessing.managers import BaseManager, BaseProxy

class AutocompletionManager(BaseManager): 
    pass

AutocompletionManager.register('AutocompletionServer', AutocompletionServer)


if __name__ == '__main__':

    if "--server" in sys.argv:
        mgr = AutocompletionManager(address=('', 50000), authkey=b'abracadabra')
        srv = mgr.get_server()
        srv.serve_forever()
    elif "--client" in sys.argv:
        mgr = AutocompletionManager(address=('', 50000), authkey=b'abracadabra')
        mgr.connect()
    else:
        mgr = AutocompletionManager()
        mgr.start()
    autocomp = mgr.AutocompletionServer()
    # = AutoComp()
    source = "import json; json.l"
    ret = autocomp.GetCompletions(source, None, 19, 1, "__main__")
    assert ret[0]["name"] == "load"
    assert ret[1]["name"] == "loads"
    source = "import json; json.load"
    ret = autocomp.GetCallTips(source, None, len(source), 1, "__main__")
    assert ret[1].startswith("Docstring for json:def load\n")
    print("tests pass ok!")
    source = "import fpdf; fpdf.FPDF"
    print(autocomp.GetCallTips(source, None, len(source),  1, ""))
    

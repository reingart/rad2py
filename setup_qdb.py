#!/usr/bin/env python

from distutils.core import setup
try:
    import py2exe
    from nsis import build_installer
except:
    build_installer = None

import qdb

setup(name='qdb',
      version=qdb.__version__,
      description='PDB-like Client/Server Debugger for Python',
      author='Mariano Reingart',
      author_email='reingart@gmail.com',
      url='http://code.google.com/p/rad2py/wiki/QdbRemotePythonDebugger',
      packages=['qdb'],
      console=['qdb/qdb.py'],
      cmdclass = {"py2exe": build_installer},
     )


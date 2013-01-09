from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext

# requires: cython

# For 64bit Windows, use "Microsoft Windows SDK v7.0" command line and do:
#    set DISTUTILS_USE_SDK=1
#    setenv /x64 /release

# To get the .pyd/dll execute at the command line: 
#    python qdb_setup.py build_ext --inplace
  
setup(
    cmdclass = {'build_ext': build_ext},
    ext_modules = [Extension("qdb_cython", ["qdb_cython.pyx"])]
)

print "Done!"
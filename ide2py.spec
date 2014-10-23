# -*- mode: python -*-

a = Analysis([os.path.join(HOMEPATH,'support\\_mountzlib.py'), 
              os.path.join(HOMEPATH,'support\\useUnicode.py'), 
              '..\\rad2py\\ide2py\\main.py',
              ], 
             pathex=['C:\\rad2py\\pyinstaller-1.5.1',
                     'C:\\rad2py\\dist\\web2py'],
             )
pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=1,
          name=os.path.join('build\\pyi.win32\\ide2py', 'ide2py.exe'),
          debug=False,
          strip=False,
          upx=True,
          console=True )
coll = COLLECT( exe,
               a.binaries,
               a.zipfiles,
               a.datas + [('ide2py.ini.dist', '..\\rad2py\\ide2py\\ide2py.ini.dist', 'DATA')],
               strip=False,
               upx=True,
               name=os.path.join('dist', 'ide2py'))

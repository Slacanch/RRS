# -*- mode: python -*-

block_cipher = None


a = Analysis(['RRS.py'],
             pathex=['/Users/tcandelli/analyses/Facility/rstudio-hpc'],
             binaries=[],
             datas=[('RRS_logo.png','.')],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='RRS',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=False , icon='RRS.icns')
app = BUNDLE(exe,
             name='RRS.app',
             icon='RRS.icns',
             bundle_identifier=None,
             info_plist={'NSHighResolutionCapable': 'True'}
             )

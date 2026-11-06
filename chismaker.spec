# -*- mode: python ; coding: utf-8 -*-
# Spec multiplataforma: Windows (.exe) y macOS (.app)
import sys

a = Analysis(
    ['chismaker.py'],
    pathex=[],
    binaries=[],
    datas=[('img/icon-cheese-32.ico', 'img')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

icon_file = 'img/icon-cheese.icns' if sys.platform == 'darwin' else 'img/icon-cheese-32.ico'

if sys.platform == 'darwin':
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name='chismaker',
        debug=False, strip=False, upx=False,
        console=False,
        icon=[icon_file],
    )
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='chismaker')
    app = BUNDLE(
        coll,
        name='SuperChis Chismaker.app',
        icon=icon_file,
        bundle_identifier='com.chisbread.chismaker',
        info_plist={'NSHighResolutionCapable': True},
    )
else:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, [],
        name='chismaker',
        debug=False, strip=False, upx=True,
        runtime_tmpdir=None,
        console=False,
        icon=[icon_file],
    )

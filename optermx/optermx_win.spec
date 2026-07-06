# -*- mode: python ; coding: utf-8 -*-

import shutil
import os

# single place to collect additional files
added_files = [
         ('Opx.conf', '.'), 
         ('polar3232.ico', '.')
         ]

a = Analysis(
    ['optermx.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='optermx',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='polar3232.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='optermx',
)

# 260529: Post-build copy hook, moves Opx.conf to prgm root
dist_dir = os.path.join('dist', 'optermx')
src_conf = 'Opx.conf'

# This guarantees the file exists in the executable's root folder after the build
if os.path.exists(src_conf) and os.path.exists(dist_dir):
    shutil.copy(src_conf, dist_dir)


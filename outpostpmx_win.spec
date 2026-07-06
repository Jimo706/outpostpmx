# -*- mode: python ; coding: utf-8 -*-

# 
# !!! VERIFY that 'opx_suite_win.spec' is in the 'C:\dev\opx' directory
# to RUN:
#   (venv)> cd C:\dev\outpostpmx
#   (venv)> python -m PyInstaller -y --clean outpostpmx_win.spec
# 

import shutil
import os
from pathlib import Path

outpostx_root = Path(r"C:\Dev\outpostpmx\outpostx")
optermx_root = Path(r"C:\Dev\outpostpmx\optermx")

# single place to collect additional files
added_files = [
         (str(outpostx_root / "polar3232.ico"), "."),
         (str(outpostx_root / "polar3232.png"), "."),
         (str(outpostx_root / "polar3232.icns"), "."),
         (str(outpostx_root / "data" / "bbs_specs"), "data/bbs_specs"),
         (str(outpostx_root / "data" / "sounds"), "data/sounds"),
         ]

# ----------
outpostx_analysis = Analysis(
    ['outpostx/outpostx.py'],
    pathex=[str(outpostx_root)],
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

optermx_analysis = Analysis(
    ['optermx/optermx.py'],
    pathex=[str(optermx_root)],
    binaries=[],
    # datas=added_files,    # 260701; avoids duplicate data 
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# ----------
outpostx_pyz = PYZ(outpostx_analysis.pure)
optermx_pyz = PYZ(optermx_analysis.pure)

# ----------
outpostx_exe = EXE(
    outpostx_pyz,
    outpostx_analysis.scripts,
    [],
    exclude_binaries=True,
    name='outpostx',
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

optermx_exe = EXE(
    optermx_pyz,
    optermx_analysis.scripts,
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

# ----------
coll = COLLECT(
    outpostx_exe,
    optermx_exe,
    outpostx_analysis.binaries,
    outpostx_analysis.datas,
    optermx_analysis.binaries,
    optermx_analysis.datas,
    strip=False,
    upx=False,          # compress later with True
    upx_exclude=[],
    name='outpostpmx',
)

# 260702: Post-build copy hook, moves Opx.conf to program root
# dist_dir = Path("dist") / "outpostpm"
# src_conf = outpostx_root / "Opx.conf"
#
# if src_conf.exists() and dist_dir.exists():
#     shutil.copy2(src_conf, dist_dir / "Opx.conf")
# else:
#     print(f"WARNING: Opx.conf copy skipped")
#     print(f"  src_conf: {src_conf} exists={src_conf.exists()}")
#     print(f"  dist_dir : {dist_dir} exists={dist_dir.exists()}")
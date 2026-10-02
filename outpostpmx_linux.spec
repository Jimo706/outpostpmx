# -*- mode: python ; coding: utf-8 -*-
# 
# to RUN:
#   cd ~/dev/outpostpmx/outpostx
#   pyinstaller --onefile --clean --name pdf_coordinate_grid tools/pdf_coordinate_grid.py
#   (Copy dist\pdf_coodinate_grid --> data\tools)
#
#   cd ~/dev/outpostpmx
#   python -m PyInstaller -y --clean outpostpmx_linux.spec
#

from pathlib import Path

suite_root = Path(".").resolve()

outpostx_root = suite_root / "outpostx"
optermx_root = suite_root / "optermx"

added_files = [
    (str(outpostx_root / "polar3232.ico"), "."),
    (str(outpostx_root / "polar3232.png"), "."),
    (str(outpostx_root / "polar3232.icns"), "."),
    (str(outpostx_root / "data" / "bbs_specs"), "data/bbs_specs"),
    (str(outpostx_root / "data" / "sounds"), "data/sounds"),
    (str(outpostx_root / "data" / "forms"), "data/forms"),
    (str(outpostx_root / "data" / "tools"), "data/tools"),      # #191 
    (str(outpostx_root / "data" / "tools.json"), "data"),       # #171
]

outpostx_analysis = Analysis(
    ["outpostx/outpostx.py"],
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
    ["optermx/optermx.py"],
    pathex=[str(optermx_root)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

outpostx_pyz = PYZ(outpostx_analysis.pure)
optermx_pyz = PYZ(optermx_analysis.pure)

outpostx_exe = EXE(
    outpostx_pyz,
    outpostx_analysis.scripts,
    [],
    exclude_binaries=True,
    name="outpostx",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

optermx_exe = EXE(
    optermx_pyz,
    optermx_analysis.scripts,
    [],
    exclude_binaries=True,
    name="optermx",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    outpostx_exe,
    optermx_exe,

    outpostx_analysis.binaries,
    outpostx_analysis.zipfiles,
    outpostx_analysis.datas,

    optermx_analysis.binaries,
    optermx_analysis.zipfiles,
    optermx_analysis.datas,

    strip=False,
    upx=False,
    name="outpostpmx",
)
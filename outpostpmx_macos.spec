# -*- mode: python ; coding: utf-8 -*-
# 
# to RUN:
#   source venv/bin/activate
#   cd ~/dev/outpostpmx/outpostx
#   pyinstaller --onefile --clean --name pdf_coordinate_grid tools/pdf_coordinate_grid.py
#   (Copy dist\pdf_coodinate_grid --> dist\outpostpmx\tools)
#
#   cd ~/dev/outpostpmx
#   python -m PyInstaller -y --clean outpostpmx_macos.spec
#
# Expected output:
#   dist/outpostpmx/
#       outpostx
#       optermx
#       _internal/
#       data/
#
# Optional packaging:
#   cd dist
#   zip -r ../release/outpostpmx-macos-x86_64.zip outpostpmx
#

from pathlib import Path
###rc2: from PyInstaller.utils.hooks import collect_submodules

suite_root = Path(SPECPATH).resolve()

outpostx_root = suite_root / "outpostx"
optermx_root = suite_root / "optermx"

# Both OutpostX and OpTermX use PySide6.
pyside6_hidden = collect_submodules("PySide6")

# Single place to collect shared suite data files.  Keep these on the OutpostX
# analysis only so they do not get duplicated in the collected app folder.
added_files = [
    (str(outpostx_root / "polar3232.ico"), "."),
    (str(outpostx_root / "polar3232.png"), "."),
    (str(outpostx_root / "polar3232.icns"), "."),
    (str(outpostx_root / "data" / "bbs_specs"), "data/bbs_specs"),
    (str(outpostx_root / "data" / "sounds"), "data/sounds"),
    (str(outpostx_root / "data" / "forms"), "data/forms"),
    (str(outpostx_root / "data" / "tools.json"), "data"),       # #171
]

outpostx_analysis = Analysis(
    [str(outpostx_root / "outpostx.py")],
    pathex=[str(outpostx_root)],
    binaries=[],
    datas=added_files,
    ###rc2: hiddenimports=[*pyside6_hidden,],
    hiddenimports=[],                           # rc2
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5"],
    noarchive=False,
    optimize=0,
)

optermx_analysis = Analysis(
    [str(optermx_root / "optermx.py")],
    pathex=[str(optermx_root)],
    binaries=[],
    datas=[],
    ###rc2: hiddenimports=pyside6_hidden,
    hiddenimports=[],                           # rc2
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5"],
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
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
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
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
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
    upx_exclude=[],
    name="outpostpmx",
)

# NOTE:
# This spec intentionally creates a suite folder, not a single .app bundle.
# A macOS .app normally has one main executable. Since the goal is a suite
# containing both outpostx and optermx, the onedir layout mirrors Windows/Linux.

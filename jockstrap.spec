# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

datas = [("LICENSE", "."), ("VERSION", "."), ("README.md", "."),
         ("THIRD_PARTY.md", "."), ("docs", "docs"), ("examples", "examples")]
binaries = []
hiddenimports = ["matplotlib.backends.backend_tkagg", "jockstrap.self_test"]
for package in ("rasterio", "pyproj"):
    package_data, package_binaries, package_imports = collect_all(package)
    datas += package_data
    binaries += package_binaries
    hiddenimports += package_imports
for package in ("itmlogic", "tkintermapview"):
    datas += collect_data_files(package)
    hiddenimports += collect_submodules(package)

a = Analysis(
    ["desktop_entry.py"], pathex=[], binaries=binaries, datas=datas,
    hiddenimports=hiddenimports, hookspath=[],
    hooksconfig={"matplotlib": {"backends": ["TkAgg", "Agg"]}},
    runtime_hooks=[], excludes=["PyQt5", "PyQt6", "PySide2", "PySide6"],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [], name="Jockstrap",
    icon="build/jockstrap.ico", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=True, hide_console="hide-early",
    disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
)

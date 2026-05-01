# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Windows desktop app.

Produces an "onedir" build at dist/motion-bg-studio/. The CI workflow then
drops ffmpeg.exe next to the launcher and zips the folder.
"""
from pathlib import Path

import sys

ROOT = Path(SPECPATH).resolve().parent
ENTRY = ROOT / "src" / "motion_bg_studio" / "app.py"

a = Analysis(
    [str(ENTRY)],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[],
    hiddenimports=[
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6.QtNetwork",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.Qt3DCore",
        "PySide6.QtMultimedia",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebChannel",
        "PySide6.QtSql",
        "PySide6.QtTest",
        "PySide6.QtPdf",
        "PySide6.QtOpenGL",
        "PySide6.QtCharts",
        "PySide6.QtBluetooth",
        "PySide6.QtPositioning",
        "PySide6.QtSensors",
        "PySide6.QtDataVisualization",
        "tkinter",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

icon_path = ROOT / "packaging" / "app.ico"
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="motion-bg-studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(icon_path) if icon_path.exists() else None,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="motion-bg-studio",
)

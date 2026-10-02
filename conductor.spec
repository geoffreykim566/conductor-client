# -*- mode: python ; coding: utf-8 -*-
import sys
sys.path.insert(0, '.')
from config import VERSION

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PIL._tkinter_finder',
        'Quartz',
        'AppKit',
        'Vision',  # Apple Vision OCR (core/capture/ocr_vision.py); dynamic pyobjc import PyInstaller can't see
        'ApplicationServices',  # AX (core/ax); same dynamic-import issue
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Conductor',
    debug=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='Conductor',
)

app = BUNDLE(
    coll,
    name='Conductor.app',
    icon=None,
    bundle_identifier='com.conductor.logicpro',
    info_plist={
        'CFBundleName': 'Conductor',
        'CFBundleDisplayName': 'Conductor',
        'CFBundleVersion': VERSION,
        'CFBundleShortVersionString': VERSION,
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '12.0',
        'NSScreenCaptureUsageDescription': (
            'Conductor captures your Logic Pro window to give Claude visual context '
            'when answering your questions.'
        ),
    },
)

# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for ZennoCall.

Build:
    pyinstaller meetily.spec --noconfirm

Output:
    dist/ZennoCall/          (one-dir bundle on all platforms)
    dist/ZennoCall.app       (macOS only)
"""
import platform
from pathlib import Path

block_cipher = None

HERE = Path(SPECPATH)
MEETILY_PKG = HERE / "meetily"
RESOURCES = MEETILY_PKG / "resources"
FONTS = MEETILY_PKG / "ui" / "fonts"

# --- Data files (source, dest_in_bundle) ---
datas = [
    (str(FONTS / "InterVariable.ttf"), "meetily/ui/fonts"),
    (str(FONTS / "JetBrainsMono.ttf"), "meetily/ui/fonts"),
    (str(RESOURCES / "icon.png"), "meetily/resources"),
]

# --- Hidden imports ---
hiddenimports = [
    "webrtcvad",
    "sounddevice",
    "soundfile",
    "numpy",
    "PySide6.QtSvg",
]

if platform.system() == "Windows":
    hiddenimports.append("pyaudiowpatch")

# --- Excluded modules (reduce bundle size) ---
excludes = [
    "tkinter",
    "unittest",
    "test",
    "xmlrpc",
    "pydoc",
    "doctest",
]

a = Analysis(
    [str(MEETILY_PKG / "main.py")],
    pathex=[str(HERE)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# --- Platform-specific icon ---
_system = platform.system()
if _system == "Darwin":
    _icon = str(RESOURCES / "icon.icns") if (RESOURCES / "icon.icns").exists() else None
elif _system == "Windows":
    _icon = str(RESOURCES / "icon.ico") if (RESOURCES / "icon.ico").exists() else None
else:
    _icon = str(RESOURCES / "icon.png") if (RESOURCES / "icon.png").exists() else None

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ZennoCall",
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
    icon=_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ZennoCall",
)

# --- macOS .app bundle ---
if _system == "Darwin":
    app = BUNDLE(
        coll,
        name="ZennoCall.app",
        icon=_icon,
        bundle_identifier="com.zennocall.app",
        info_plist={
            "NSMicrophoneUsageDescription": (
                "ZennoCall needs microphone access to record meetings."
            ),
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": "0.1.0",
            "LSMinimumSystemVersion": "12.0",
        },
    )

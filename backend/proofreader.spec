# proofreader.spec
# Run with: pyinstaller proofreader.spec

import sys
import os
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Collect everything fastapi, uvicorn, and starlette need at runtime
datas = []
binaries = []
hiddenimports = []

for pkg in ["fastapi", "uvicorn", "starlette", "anyio", "httptools", "websockets", "playwright"]:
    d, b, h = collect_all(pkg)
    datas    += d
    binaries += b
    hiddenimports += h

# Include your config.json so the packaged app can read it
datas += [("config.json", ".")]

# If you have a prompts/ or checks/ folder with data files, include them too
if os.path.isdir("prompts"):
    datas += [("prompts", "prompts")]
if os.path.isdir("checks"):
    datas += [("checks", "checks")]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + [
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "playwright.sync_api",
        "playwright.async_api",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="backend",          # produces backend.exe on Windows, backend on Linux
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # no console window on Windows
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
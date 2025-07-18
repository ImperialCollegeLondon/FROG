# -*- mode: python ; coding: utf-8 -*-
from frog.hardware.plugins import load_all_plugins

from pathlib import Path
import sys

# Generate user guide with pandoc
repo_root = str(Path(sys.argv[0]).parent.parent)
sys.path.append(repo_root)
import docs.gen_user_guide as gen_guide

block_cipher = None

gen_guide.generate_html()

a = Analysis(
    ["stub.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("frog/gui/hardware_set/*.yaml", "frog/gui/hardware_set"),
        ("frog/gui/images/*.png", "frog/gui/images"),
        (
            "frog/hardware/plugins/sensors/diag_autom.htm",
            "frog/hardware/plugins/sensors",
        ),
        ("../docs/user_guide.html", "docs"),
        ("../docs/fallback.html", "docs"),
    ],
    hiddenimports=["frog.gui.images", *load_all_plugins()],
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
    name="FROG",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

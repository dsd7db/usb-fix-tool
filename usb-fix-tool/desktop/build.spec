# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for USB Fix Tool.

Build (on Windows):
    pip install pyinstaller
    pyinstaller build.spec

The resulting executable lives in `dist/USBFixTool/USBFixTool.exe`.

Notes for AV friendliness:
    - We DO NOT use --onefile (single-exe extracts to %TEMP% which some
      antivirus engines flag).
    - We keep `console=False` so a stray cmd window never opens, but
      we sign nothing exotic and embed a normal Windows manifest that
      requests admin rights via UAC (no token tricks).
"""

block_cipher = None


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets')],   # bundle SVG checkmark + future assets
    hiddenimports=[],
    hookspath=[],
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
    [],
    exclude_binaries=True,
    name='USBFixTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,            # UPX-packed binaries get flagged by AVs
    console=False,
    uac_admin=True,       # request administrator rights via UAC
    icon='assets/app.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='USBFixTool',
)

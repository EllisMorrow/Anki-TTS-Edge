# -*- mode: python ; coding: utf-8 -*-
import os
import shutil

from PyInstaller.utils.hooks import collect_all

datas = [('Anki-TTS-Flet/assets', 'assets')]
binaries = []
hiddenimports = ['pystray', 'PIL', 'pygame', 'pynput', 'win32clipboard', 'win32con', 'flet', 'flet_desktop']
tmp_ret = collect_all('edge_tts')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('flet')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('flet_desktop')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['Anki-TTS-Flet\\main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Anki-TTS-Edge',
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
    icon=['Anki-TTS-Flet\\assets\\icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Anki-TTS-Edge',
)

# PyInstaller 6 places collected data under _internal. Legal notices must also
# remain visible next to the executable in the distributable onedir package.
for legal_filename in ('LICENSE', 'NOTICE'):
    shutil.copy2(
        os.path.join(SPECPATH, legal_filename),
        os.path.join(DISTPATH, 'Anki-TTS-Edge', legal_filename),
    )

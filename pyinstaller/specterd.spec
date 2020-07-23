# -*- mode: python ; coding: utf-8 -*-
import platform
import subprocess
import mnemonic, os

mnemonic_path = os.path.join(mnemonic.__path__[0], "wordlist")

block_cipher = None

binaries = []
if platform.system() == 'Windows':
    binaries = [("c:/python3/libusb-1.0.dll", ".")]
elif platform.system() == 'Linux':
    binaries = [("/lib/x86_64-linux-gnu/libusb-1.0.so.0", ".")]
elif platform.system() == 'Darwin':
    find_brew_libusb_proc = subprocess.Popen(['brew', '--prefix', 'libusb'], stdout=subprocess.PIPE)
    libusb_path = find_brew_libusb_proc.communicate()[0]
    binaries = [(libusb_path.rstrip().decode() + "/lib/libusb-1.0.dylib", ".")]

a = Analysis(['specterd.py'],
             # pathex=['/Users/ss/dev/web/myspecter/pyinstaller'],
             binaries=binaries,
             datas=[('../src/cryptoadvance/specter/templates', 'templates'), 
                    ('../src/cryptoadvance/specter/static', 'static'),
                    (mnemonic_path, 'mnemonic/wordlist'),
             ],
             hiddenimports=['_cffi_backend'],
             hookspath=['hooks/'],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='specterd',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=True )

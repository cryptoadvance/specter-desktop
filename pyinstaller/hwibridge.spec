# -*- mode: python ; coding: utf-8 -*-
import platform
import subprocess
import mnemonic, os
from embit import util as embit_util

mnemonic_path = os.path.join(mnemonic.__path__[0], "wordlist")
embit_libsecp_binary = embit_util.ctypes_secp256k1._find_library()

block_cipher = None

binaries = []
if platform.system() == 'Windows':
    binaries = [("./windll/libusb-1.0.dll", ".")]
elif platform.system() == 'Linux':
    if platform.processor() == 'aarch64': #ARM 64 bit
        binaries = [("/lib/aarch64-linux-gnu/libusb-1.0.so.0", ".")]
    else:
        binaries = [("/lib/x86_64-linux-gnu/libusb-1.0.so.0", ".")]
elif platform.system() == 'Darwin':
    find_brew_libusb_proc = subprocess.Popen(['brew', '--prefix', 'libusb'], stdout=subprocess.PIPE)
    libusb_path = find_brew_libusb_proc.communicate()[0]
    binaries = [(libusb_path.rstrip().decode() + "/lib/libusb-1.0.dylib", ".")]

a = Analysis(['hwibridge.py'],
             binaries=binaries,
             datas=[('../src/cryptoadvance/specter/templates', 'templates'), 
                    ('../src/cryptoadvance/specter/static', 'static'),
                    ('../src/cryptoadvance/specter/translations', 'translations'),
                    (mnemonic_path, 'mnemonic/wordlist'),
                    (embit_libsecp_binary, 'embit/util/prebuilt'),
             ],
             hiddenimports=[
                'pkg_resources.py2_warn',
                'cryptoadvance.specter.config'
             ],
             hookspath=['hooks/'],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

if platform.system() == 'Linux':
    import hwilib
    a.datas += Tree('../udev', prefix='hwilib/udev')

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='hwibridge',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=True )

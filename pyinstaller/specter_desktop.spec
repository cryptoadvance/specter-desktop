# -*- mode: python ; coding: utf-8 -*-
import platform
import subprocess
import mnemonic, os, sys

mnemonic_path = os.path.join(mnemonic.__path__[0], "wordlist")

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

a = Analysis(['specter_desktop.py'],
             binaries=binaries,
             datas=[('../src/cryptoadvance/specter/templates', 'templates'), 
                    ('../src/cryptoadvance/specter/static', 'static'),
                    ('./specterd', 'specterd'),
                    (mnemonic_path, 'mnemonic/wordlist'),
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
          name='Specter',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=True,
          icon='../src/cryptoadvance/specter/static/img/icon.icns' )

if sys.platform == 'darwin':
   app = BUNDLE(exe,
                name='Specter.app',
                icon='../src/cryptoadvance/specter/static/img/icon.icns',
                bundle_identifier=None,
                info_plist={
                    'NSPrincipleClass': 'NSApplication',
                    'NSAppleScriptEnabled': False,
                    'NSHighResolutionCapable': 'True',
                    'NSRequiresAquaSystemAppearance': 'True',
                    'LSUIElement': 1
                })
if sys.platform == 'win32' or sys.platform == 'win64' or sys.platform == 'linux':
  exe = EXE(pyz,
            a.scripts,
            a.binaries,
            a.zipfiles,
            a.datas,
            name='Specter',
            debug=False,
            strip=False,
            upx=True,
            runtime_tmpdir=None,
            console=False,
            icon='../src/cryptoadvance/specter/static/img/icon.ico')

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
    arch = platform.processor()
    binaries = [(f"/lib/{arch}-linux-gnu/libusb-1.0.so.0", "."),
                (f"/usr/lib/{arch}-linux-gnu/dri/iris_dri.so","."),
                (f"/usr/lib/{arch}-linux-gnu/gio/modules/libgvfsdbus.so","."),
                (f"/usr/lib/{arch}-linux-gnu/gvfs/libgvfscommon.so","."),
                (f"/usr/lib/{arch}-linux-gnu/gtk-3.0/modules/libcanberra-gtk3-module.so","."),
                (f"/usr/lib/{arch}-linux-gnu/libcanberra-gtk3.so.0","."),
                (f"/usr/lib/{arch}-linux-gnu/libcanberra.so.0","."),
                (f"/usr/lib/{arch}-linux-gnu/libdrm_amdgpu.so.1","."),
                (f"/usr/lib/{arch}-linux-gnu/libdrm_nouveau.so.2","."),
                (f"/usr/lib/{arch}-linux-gnu/libdrm_radeon.so.1","."),
                (f"/usr/lib/{arch}-linux-gnu/libedit.so.2","."),
                (f"/usr/lib/{arch}-linux-gnu/libelf.so.1","."),
                (f"/usr/lib/{arch}-linux-gnu/libLLVM-10.so.1","."),
                (f"/usr/lib/{arch}-linux-gnu/libltdl.so.7","."),
                (f"/usr/lib/{arch}-linux-gnu/libsensors.so.4","."),
                (f"/usr/lib/{arch}-linux-gnu/libtdb.so.1","."),
    ]
elif platform.system() == 'Darwin':
    find_brew_libusb_proc = subprocess.Popen(['brew', '--prefix', 'libusb'], stdout=subprocess.PIPE)
    libusb_path = find_brew_libusb_proc.communicate()[0]
    binaries = [(libusb_path.rstrip().decode() + "/lib/libusb-1.0.dylib", ".")]

a = Analysis(['specter_desktop.py'],
             binaries=binaries,
             datas=[('../src/cryptoadvance/specter/templates', 'templates'), 
                    ('../src/cryptoadvance/specter/static', 'static'),
                    ("./icons", "icons"),
                    (mnemonic_path, 'mnemonic/wordlist'),
                    ("version.txt", "."),
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

if sys.platform == 'darwin':

    exe = EXE(pyz,
          a.scripts,
          [],
          name='Specter',
          exclude_binaries=True,
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=True )

    app = BUNDLE(
          exe,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='Specter.app',
          icon='icons/icon.icns',
          bundle_identifier=None,
          info_plist={
            'NSPrincipleClass': 'NSApplication',
            'NSAppleScriptEnabled': False,
            'NSHighResolutionCapable': 'True',
            'NSRequiresAquaSystemAppearance': 'True',
            'LSUIElement': 1
        }
    )
if sys.platform == 'linux':
    exe = EXE(
        pyz,
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
        icon='icons/icon.ico'
    )

if sys.platform == 'win32' or sys.platform == 'win64':
    exe = EXE(pyz,
              a.scripts,
              [],
              exclude_binaries=True,
              name='specter_desktop',
              debug=False,
              bootloader_ignore_signals=False,
              strip=False,
              upx=True,
              console=False,
              icon='icons/icon.ico' )

    coll = COLLECT(exe,
                   a.binaries,
                   a.zipfiles,
                   a.datas,
                   strip=False,
                   upx=True,
                   upx_exclude=[],
                   console=False,
                   name='specter_desktop')
 
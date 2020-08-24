# Pyinstaller build

Install `pyinstaller`:
```bash
$ pip3 install -r requirements.txt
```

`cd` into this directory (`specter-desktop/pyinstaller`) and run:
```bash
$ pyinstaller specterd.spec
```

And for HWIBridge, run: 
```bash
pyinstaller hwibridge.spec
```

# Building Specter launcher (tray app)

## Creating a Windows setup file

From Powershell:

1. Build `specterd` and `hwibridge` in onedir mode:

```bash
pyinstaller specterd_onedir.spec
pyinstaller hwibridge_onedir.spec
```

You should get two folders in the `dist` folder: `specterd` and `hwibridge`.

2. Copy `specterd` folder from `dist` folder to this directory.
3. Copy `hwibridge.exe` and `hwibridge.exe.manifest` from `dist\hwibridge\` to `specterd` folder.
4. Run `pyinstaller specter_desktop.spec` - this should create a `specter_desktop` folder in the `dist` directory. Check that it works by running `dist\specter_desktop\specter_desktop.exe`
5. Create an installer using [InnoSetup](https://jrsoftware.org/isdl.php#stable), select `dist\specter_desktop\specter_desktop.exe` as main executable, add `dist\specter_desktop` folder to the setup wizard as well.

## Creating a DMG for macOS

1. Build `specterd` and `hwibridge` in onedir mode:

```bash
pyinstaller specterd_onedir.spec
pyinstaller hwibridge_onedir.spec
```

You should get two folders in the `dist` folder: `specterd` and `hwibridge`.

2. Copy `specterd` folder from `dist` folder to this directory: `cp -r dist/specterd/ ./specterd`
3. Copy `hwibridge` binary from `dist/hwibridge` to `specterd` folder: `cp dist/hwibridge/hwibridge specterd`.
4. Now in the terminal, run `pyinstaller specter_desktop.spec` (you might need to use sudo). This should create a new Specter and Specter.app files.
5. The `Specter.app` file is the executable macOS app we will need to package now as a `.dmg` for distribution.
6. Make sure you have [`NPM`](https://www.npmjs.com/get-npm) installed, and run `npm install --global create-dmg`.
7. Now run `create-dmg 'dist/Specter.app'`. This should generate a new `Specter 0.0.0.dmg`.
8. The `.dmg` should now be ready to use! Note: You can rename the `.dmg` file to have the proper version (or just say `Specter`).

## Creating a binary for Linux

1. Build `specterd` and `hwibridge` in onedir mode:

```bash
pyinstaller specterd_onedir.spec
pyinstaller hwibridge_onedir.spec
```

You should get two folders in the `dist` folder: `specterd` and `hwibridge`.

2. Copy `specterd` folder from `dist` folder to this directory: `cp -r dist/specterd/ ./specterd`
3. Copy `hwibridge` binary from `dist/hwibridge` to `specterd` folder: `cp dist/hwibridge/hwibridge specterd`.
4. Run `pyinstaller specter_desktop.spec`. This should create a Specter executable.


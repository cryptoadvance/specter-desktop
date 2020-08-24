# Pyinstaller build

Install `pyinstaller`:
```bash
$ pip3 install pyinstaller
```

`cd` into this directory (`specter-desktop/pyinstaller`) and run:
```bash
$ pyinstaller specterd.spec
```

And for HWIBridge, run: 
```bash
pyinstaller hwibridge.spec
```

## Building launcher for Windows

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
5. Create an installer using [InnoSetup](https://jrsoftware.org/isdl.php#stable)

## Creating a Specter Desktop DMG (macOS only)

1. First, follow the steps above to create an up-to-date `specterd` and `hwibridge` executables.
2. Copy the executables from the `dist` folder and place it under the `specterd` folder.
3. Now in the terminal, run `pyinstaller --onefile specter_desktop.spec` (you might need to use `sudo`). This should create a new `Specter` and `Specter.app` files.
4. The `Specter.app` file is the executable macOS app we will need to package now as a `.dmg` for distribution.
5. Make sure you have [`NPM`](https://www.npmjs.com/get-npm) installed, and run `npm install --global create-dmg`.
6. Now run `create-dmg 'dist/Specter.app'`. This should generate a new `Specter 0.0.0.dmg`.
7. The `.dmg` should now be ready to use! Note: You can rename the `.dmg` file to have the proper version (or just say `Specter`).

# Build scripts

Run `build-<your-os> <version_number>` file to build everything.

For example, `build-osx.sh 1.2.3` will create `SpecterDesktop-1.2.3.dmg` and `specterd-1.2.3-osx.zip` in the `release` folder.

On Windows `release` folder is empty, but `dist` folder contains a `specter_desktop` folder for inno setup and `specterd.exe` binary.

# Pyinstaller build

`cd` into this directory (`specter-desktop/pyinstaller`) and install requirements:

```bash
$ pip3 install -r requirements.txt --require-hashes
```

Now run:

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

1. Build `specterd` in onedir mode:

```bash
pyinstaller specterd_onedir.spec
```

You should get a `specterd` directory in the `dist` folder.

2. Copy `specterd` folder from `dist` folder to this directory.
3. Run `pyinstaller specter_desktop.spec` - this should create a `specter_desktop` folder in the `dist` directory. Check that it works by running `dist\specter_desktop\specter_desktop.exe`
4. Create an installer using [InnoSetup](https://jrsoftware.org/isdl.php#stable), select `dist\specter_desktop\specter_desktop.exe` as main executable, add `dist\specter_desktop` folder to the setup wizard as well.

## Creating a DMG for macOS

*Note*: pyinstaller doesn't fully support python3.8 at the moment, use python3.7.

1. Build `specterd` in onedir mode:

```bash
pyinstaller specterd_onedir.spec
```

You should get a `specterd` directory in the `dist` folder.

2. Copy `specterd` folder from `dist` folder to this directory: `cp -r dist/specterd/ ./specterd`
3. Now in the terminal, run `pyinstaller specter_desktop.spec` (you might need to use sudo). This should create a new Specter and Specter.app files.
4. The `Specter.app` file is the executable macOS app we will need to package now as a `.dmg` for distribution.
5. Make sure you have [`NPM`](https://www.npmjs.com/get-npm) installed, and run `npm install --global create-dmg`.
6. Now run `create-dmg 'dist/Specter.app'`. This should generate a new `Specter 0.0.0.dmg`.
7. The `.dmg` should now be ready to use! Note: You can rename the `.dmg` file to have the proper version (or just say `Specter`).

## Creating a binary for Linux

1. Build `specterd` in onedir mode:

```bash
pyinstaller specterd_onedir.spec
```

You should get a `specterd` directory in the `dist` folder.

2. Copy `specterd` folder from `dist` folder to this directory: `cp -r dist/specterd/ ./specterd`
3. Run `pyinstaller specter_desktop.spec`. This should create a Specter executable.


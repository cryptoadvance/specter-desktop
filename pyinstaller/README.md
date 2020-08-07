# Pyinstaller build

To build a binary: `pip3 install pyinstaller`

Then from this folder run `pyinstaller --onefile specterd.spec`
And for HWIBridge, run run `pyinstaller --onefile hwibridge.spec`

## Creating a Specter Desktop DMG (macOS only)
1. First, follow the steps above to create an up-to-date `specterd` and `hwibridge` executables.
2. Copy the executables from the `dist` folder and place it under the `specterd` folder.
3. Now in the terminal, run `pyinstaller --onefile specter_desktop.spec` (you might need to use `sudo`). This should create a new `Specter` and `Specter.app` files.
4. The `Specter.app` file is the executable macOS app we will need to package now as a `.dmg` for distribution.
5. Make sure you have [`NPM`](https://www.npmjs.com/get-npm) installed, and run `npm install --global create-dmg`.
6. Now run `create-dmg 'dist/Specter.app'`. This should generate a new `Specter 0.0.0.dmg`.
7. The `.dmg` should now be ready to use! Note: You can rename the `.dmg` file to have the proper version (or just say `Specter`).

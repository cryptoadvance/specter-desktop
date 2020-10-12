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

## Code signing the macOS app for Apple GateKeeper

*Note: for this, you'll need to have an active Apple Developer account*

If this is the first time you go through this process, you'll need to first set up the following:

### Apple Developer Certificate for Code-Signing
1. Go to the Apple Developer website: https://developer.apple.com
2. Click `Account` -> `Certificates, Identifiers & Profiles`
3. Click the `+` icon to create a new certificate. Select `Developer ID Application` and click `Continue`
4. You'll need now to create a certificate signing request, which you can do by following these instructions: https://help.apple.com/developer-account/#/devbfa00fef7, After that you should be able to generate and download the certificate.
5. Download the certificate, then double-click the downloaded certificate to install it in your keychain.

### App Specific Password for authenticating to iTunesConnect for notarization
1. Sign into you Apple ID account: https://appleid.apple.com
2. Go to `Security` -> `App Specific Passwords` and click `Generate Password…`, you'll be asked to enter a label and click `Create`, then you'll receive a new password.
3. Copy the password generated, then open the Terminal and run:
```bash
xcrun altool --store-password-in-keychain-item "AC_PASSWORD" -u "<your-apple-id>" -p "<the-generated-password>"
```

After having these set up, you can use the automated script to sign by passing it 2 extra parameters: 
- Your certificate name, which you can see on the Keychain app going to the sidebar -> `My Certificates` and copying the name of the certificate you've created in step 1.
- Your Apple ID.

With these two, you can run the command like so:
```bash
./build-osx.sh <version_number> "<certificate_name>" "<apple_id>"
```

This could take about an hour, during which you should receive an email from Apple notifying whatever the notarization was successful.
If for some reason the notarization failed, you'll be able to get the reason by copying the `Request Identifier` (you should be able to find this in the email and in the logs).
Then run the following command:
```bash
xcrun altool --verbose --notarization-info <request_identifier> -u "<apple_id>" -p "@keychain:AC_PASSWORD"
```
This will output a long message, at the end of which you should have be able to find the `LogFileURL:`.
This URL should contain a JSON with the issues found by Apple and which you'll need to fix to be able to pass Apple's notarization.

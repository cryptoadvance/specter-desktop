# Pyinstaller build

Releases are built by `.github/workflows/release.yml` (triggered by a version tag). The notes below are for local / manual builds.

Install requirements:

```bash
virtualenv --python=python3 .buildenv
source .buildenv/bin/activate 
pip3 install -r requirements.txt --require-hashes
cd pyinstaller
pip3 install -r requirements.txt --require-hashes
```

Now run:

```bash
pyinstaller specterd.spec
```

And for HWIBridge, run: 

```bash
pyinstaller hwibridge.spec
```

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

Release builds sign and notarize via `.github/workflows/release.yml` (`build-electron-macos` job) using the `APPLE_CERTIFICATE_BASE64`, `APPLE_CERTIFICATE_PASSWORD`, `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, and `APPLE_TEAM_ID` secrets. See `docs/release-guide.md` for the full secret inventory. For manual local signing, use `electron-builder` directly (`npm run dist -- --mac` in `pyinstaller/electron/`, with the identity configured in `package.json`).

Notarization takes ~10 minutes, during which Apple emails notification of success/failure.
If for some reason the notarization failed, you'll be able to get the reason by copying the `Request Identifier` (you should be able to find this in the email and in the logs).
Then run the following command:
```bash
xcrun altool --verbose --notarization-info <request_identifier> -u "<apple_id>" -p "@keychain:AC_PASSWORD"
```
This will output a long message, at the end of which you should have be able to find the `LogFileURL:`.
This URL should contain a JSON with the issues found by Apple and which you'll need to fix to be able to pass Apple's notarization.

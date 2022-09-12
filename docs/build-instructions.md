# Build System
Ideally, a software-project has a build-system and a continuous-integration-system. The build-system takes care of being able to build the artifacts on your local (developer-) machine.
The continuous-integration-system takes care of using the build-system to do the same in a release-context on build-runners/-agents.

This document addresses the build-system part. For the continuous-integration-part, please have a look at [continuous-integration.md](./continuous-integration.md).

## pip-packages
```
# in the case of a release, the version needs to be adapted:
# sed -i "s/version=\".*/version=\"$CI_COMMIT_TAG\",/" setup.py

python3 setup.py sdist bdist_wheel
cryptoadvance.specter-vx.y.z-get-replaced-by-release-script.tar.gz
```
This process is the same for all platforms. The result unfortunately is not stable in terms of identically sh256-hashes, though.

## Electron
The electron build is assuming a node-installation. So make sure you have `node` and `npm` available.

The electron-app is built in a way that it's running the `specterd` (specter-demon) internally. It's not bundled with the electron-binary but downloaded with the first start (including sha256- and gpg-verification). 
If someone does not want the download, he can manually choose a specterd-binary from the `preferences/Advanced` menu. Nevertheless the Electron-App is tied, at buildtime, to a specific specterd-binary via a sha256-version. This probably doesn't make so much sense if you build outside of a release but we need it anyway.

So let's cover the build of the specterd-binary first. Below is a manual description of the build-process. There are acripts which are doing this but they are partially optimized for the CI-system. Check the `pyinstaller/build-*` scripts for details.

First set the virtualenv:

```bash
virtualenv --python=python3 .buildenv
source .buildenv/bin/activate 
```

### specterd Linux and MacOS

Below doesn't seem to work properly, at least on MacOS, better use the build script. For MacOS, that would be:
```bash
./utils/build-osx.sh --version 0.0.0-pre1 specterd
```

```bash
cd pyinstaller
# prerequisites
pip3 install -r requirements.txt --require-hashes
pip3 install -e ..
# cleaning up
rm -rf build/ dist/ release/ electron/release/ electron/dist release-linux/ release-win/
pyinstaller specterd.spec
# The binary i in dist/specterd
ls dist
```

### specterd Windows
The windows build for specterd is quite similiar:
```
pip3 install -r requirements.txt  --require-hashes
pip3 install -e ..
rmdir /s /q .\dist\
rmdir /s /q .\build\
rmdir /s /q .\release\
rmdir /s /q .\electron\dist\
pyinstaller.exe specterd.spec
```

### Electron Linux
The prerequisite for an electron build is a successfull specterd-build above. So now we need to bake the hash and a way how to retrieve the specterd-file when the electron-app is started:
```bash
cd electron
# You have to decide about a version
npm i
node ./set-version v1.3.1-custom ../dist/specterd
```

this will create a file `version-data.json` which looks like this:
```
{
  "version": "v1.3.1-custom",
  "sha256": "221b7f672e7051beebec57647fcb1c254df5964492803a1c04e7738b8af8c9f8"
}
```

Now we can create the electron-App:
```
npm run dist -- --linux
ls dist
```

So now we can start the App-Image and the first thing it will do is trying to download the specterd from the specter-desktop-github-release-page. But obviously it's not there and so it will report an error:
```
Fetching specter binary from the server failed, could not reach the server or the file could not have been found.
```
So now you can open the preferences/Advanced and choose your local specterd which will get checked against the hash calculated above and copied into `~/.specter/specterd-binaries`.

### Electron MacOS
The Electron build for MacOS is a bit more complex as there is some signing involved. You can do the build via the script:
```
cd electron
npm ci
node ./set-version v1.3.1-custom ../dist/specterd

npm i
# We assume here that no Apple-developer-ID is used to sign the binary.
# Check `build-osx.sh` if you want to sign
echo "`jq '.build.mac.identity=null' package.json`" > package.json

# finally build
npm run dist

cd ..
mkdir release
create-dmg 'electron/dist/mac/Specter.app' --identity="Developer ID Application: "
ls -l ./release/*.dmg
```

### Electron Windows
```
cd electron
call npm ci
call node ./set-version "v1.3.1-custom" "../dist/specterd.exe"

call npm i
call npm run dist
cd ..
dir -l "electron\dist\Specter Setup *.exe"
```

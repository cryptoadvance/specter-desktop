#!/usr/bin/env bash
set -exo
# possible prerequisites
# brew install gmp # to prevent module 'embit.util' has no attribute 'ctypes_secp256k1'
# npm install --global create-dmg

# Download into torbrowser:
# wget -P torbrowser https://archive.torproject.org/tor-package-archive/torbrowser/10.0.15/TorBrowser-10.0.15-osx64_en-US.dmg

# Currently, only MacOS Catalina is supported to build the dmg-file
# Therefore we expect xcode 12.1 (according to google)
# After installation of xcode: sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
# otherwise you get xcrun: error: unable to find utility "altool", not a developer tool or in PATH

# Fill the keychain with your password like this
# xcrun altool --store-password-in-keychain-item AC_PASSWORD -u '<your apple id>' -p apassword

# You need to participate in the Apple-Developer Program (Eur 99,- yearly fee)
# https://developer.apple.com/programs/enroll/ 

# Then you need to create a cert which you need to store in the keychain
# https://developer.apple.com/account/resources/certificates/list

# If you have the common issue "errSecInternalComponent" while signing the code:
# https://medium.com/@ceyhunkeklik/how-to-fix-ios-application-code-signing-error-4818bd331327

# create-dmg issue? Note that there are 2 create-dmg scripts out there. We use:
# https://github.com/sindresorhus/create-dmg

# Example-call:
# ./build-osx.sh v1.6.1-pre1 "Kim Neunert (FWV59JHV83)" "kneunert@gmail.com" "make-hash"

echo $1 > version.txt
pip3 install -r requirements.txt --require-hashes
pip3 install -e ..
cd ..
python3 setup.py install
cd pyinstaller
rm -rf build/ dist/ release/ electron/release/ electron/dist
rm *.dmg || true
pyinstaller specterd.spec
cd electron
npm ci
if [[ "$4" == 'make-hash' ]]
then
    node ./set-version $1 ../dist/specterd
else
    node ./set-version $1
fi
npm i
if [[ "$2" == '' ]]
then
    echo "`jq '.build.mac.identity=null' package.json`" > package.json
else
    echo "`jq '.build.mac.identity="'"$2"'"' package.json`" > package.json
fi
npm run dist

if [[ "$2" != '' ]]
then
    echo 'Attempting to code sign...'
    ditto -c -k --keepParent "dist/mac/Specter.app" dist/Specter.zip
    output_json=$(xcrun altool --notarize-app -t osx -f dist/Specter.zip --primary-bundle-id "solutions.specter.desktop" -u "$3" --password "@keychain:AC_PASSWORD" --output-format json)
    echo "JSON-Output:"
    requestuuid=$(echo $output_json | jq -r '."notarization-upload".RequestUUID')
    sleep 180
    sign_result_json=$(xcrun altool --notarization-info $requestuuid -u "$3" --password "@keychain:AC_PASSWORD" --output-format json)
    mkdir -p signing_logs
    timestamp=$(date +"%Y%m%d-%H%M")
    echo $sign_result_json | jq . > ./signing_logs/${timestamp}_${requestuuid}.log
    xcrun stapler staple "dist/mac/Specter.app"
fi

cd ..

mkdir release

create-dmg 'electron/dist/mac/Specter.app' --identity="Developer ID Application: $2"
mv "Specter ${1:1}.dmg" release/SpecterDesktop-$1.dmg

cd dist
zip ../release/specterd-$1-osx.zip specterd
cd ..

sha256sum ./release/specterd-$1-osx.zip
sha256sum ./release/SpecterDesktop-$1.dmg

# "In order to upload these artifacts to github, do:"
# export CI_PROJECT_ROOT_NAMESPACE=cryptoadvance
# export CI_COMMIT_TAG=$1
# export GH_BIN_UPLOAD_PW=YourSecretHere
# python ./utils/github.py upload ./release/specterd-$1-osx.zip
# python ./utils/github.py upload ./release/SpecterDesktop-$1.dmg
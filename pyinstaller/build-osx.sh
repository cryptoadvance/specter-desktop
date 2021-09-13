#!/usr/bin/env bash
set -exo
# possible prerequisites
# brew install gmp # to prevent module 'embit.util' has no attribute 'ctypes_secp256k1'

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
    echo "Error-Results for notarisation"
    echo $output_json | jq '."product-errors"[]'
    sleep 180
    # xcrun altool --notarization-info 0c517c14-2a1a-4df9-8870-3d8865e447ef -u "$3" --password "@keychain:AC_PASSWORD"
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

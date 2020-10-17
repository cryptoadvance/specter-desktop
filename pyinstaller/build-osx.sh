#!/usr/bin/env bash

# pass version number as an argument 

echo $1 > version.txt
pip install -r requirements.txt --require-hashes
pip install -e ..
rm -rf build/ dist/ release/ electron/release/ electron/dist
rm *.dmg
pyinstaller specterd.spec
brew install jq
cd electron
npm ci
echo "`jq '.version="'"$1"'"' package.json`" > package.json
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
    xcrun altool --notarize-app -t osx -f dist/Specter.zip --primary-bundle-id "solutions.specter.desktop" -u "$3" --password "@keychain:AC_PASSWORD"
    sleep 180
    xcrun stapler staple "dist/mac/Specter.app"
fi

cd ..

mkdir release

create-dmg 'electron/dist/mac/Specter.app' --identity="Developer ID Application: $2"
mv "Specter $1.dmg" release/SpecterDesktop-$1.dmg
zip release/specterd-$1-osx.zip dist/specterd

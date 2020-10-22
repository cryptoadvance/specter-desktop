#!/usr/bin/env bash

echo $1 > version.txt
pip install -r requirements.txt --require-hashes
pip install -e ..
rm -rf build/ dist/ release/ electron/release/ electron/dist
rm *.dmg
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
    xcrun altool --notarize-app -t osx -f dist/Specter.zip --primary-bundle-id "solutions.specter.desktop" -u "$3" --password "@keychain:AC_PASSWORD"
    sleep 180
    xcrun stapler staple "dist/mac/Specter.app"
fi

cd ..

mkdir release

create-dmg 'electron/dist/mac/Specter.app' --identity="Developer ID Application: $2"
mv "Specter ${1:1}.dmg" release/SpecterDesktop-$1.dmg

cd dist
zip ../release/specterd-$1-osx.zip specterd
cd ..

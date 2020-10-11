#!/usr/bin/env bash

# pass version number as an argument 

echo $1 > version.txt
pip install -r requirements.txt --require-hashes
pip install -e ..
rm -rf build/ dist/ release/
rm *.dmg
pyinstaller specter_desktop.spec
pyinstaller specterd.spec

mkdir release

create-dmg 'dist/Specter.app'
mv "Specter 0.0.0.dmg" release/SpecterDesktop-$1.dmg
zip release/specterd-$1-osx.zip dist/specterd

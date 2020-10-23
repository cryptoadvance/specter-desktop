#!/usr/bin/env bash

# pass version number as an argument 

echo $1 > version.txt
pip3 install -r requirements.txt --require-hashes
pip3 install -e ..
rm -rf build/ dist/ release/ electron/release/ electron/dist
pyinstaller specterd.spec
cd electron
npm ci

# calculate the hash of the binary for download
if [[ "$2" == 'make-hash' ]]
then
    node ./set-version $1 ../dist/specterd
else
    node ./set-version $1
fi

# build electron app
npm i
npm run dist
cd ..

# copy everything to release folder
mkdir release
cd dist
cp -r ../../udev ./udev
echo "Don't forget to set up udev rules! Check out udev folder for instructions." > README.md
zip -r ../release/specterd-$1-`arch`-linux-gnu.zip specterd udev README.md

cp ../electron/dist/Specter-* ./
tar -czvf ../release/specter_desktop-$1-`arch`-linux-gnu.tar.gz Specter-* udev README.md

cd ..

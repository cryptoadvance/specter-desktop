#!/usr/bin/env bash

# pass version number as an argument 

echo $1 > version.txt
pip3 install -r requirements.txt --require-hashes
pip3 install -e ..
rm -rf build/ dist/ release/ electron/release/ electron/dist release-linux/ release-win/
pyinstaller specterd.spec
cd electron
npm ci
node ./set-version $1 ../dist/specterd

# build electron app
npm i
npm run dist -- --linux
cd ..

# copy everything to release folder
mkdir release-linux
cd dist
cp -r ../../udev ./udev
echo "Don't forget to set up udev rules! Check out udev folder for instructions." > README.md
zip -r ../release-linux/specterd-$1-`arch`-linux-gnu.zip specterd udev README.md

cp ../electron/dist/Specter-* ./
tar -czvf ../release-linux/specter_desktop-$1-`arch`-linux-gnu.tar.gz Specter-* udev README.md

cd ..
rm -rf dist
mkdir dist
cd dist
wget https://github.com/cryptoadvance/specter-desktop/releases/download/$1/specterd-$1-win64.zip -O ./specterd.zip
unzip specterd.zip
cd ../electron
rm -rf dist/
npm ci
node ./set-version $1 ../dist/specterd.exe
npm run dist -- --win
cd ..

mkdir release-win
cp electron/dist/Specter\ Setup\ *.exe release-win/Specter\ Setup\ $1.exe

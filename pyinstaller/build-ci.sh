#!/usr/bin/env bash

set -e

# pass version number as an argument 

echo "    --> This build got triggered for version $1"

echo "    --> Assumed gitlab-project: ${CI_PROJECT_ROOT_NAMESPACE:+x}"

[ -z "${CI_PROJECT_ROOT_NAMESPACE:+x}" ]    && \
    echo "Redefining CI_PROJECT_ROOT_NAMESPACE=cryptoadvance " && \
    export CI_PROJECT_ROOT_NAMESPACE=cryptoadvance

echo $1 > version.txt
echo "    --> Installing (build)-requirements"
pip3 install -r requirements.txt --require-hashes
cd ..
python3 setup.py install
pip3 install -e .
cd pyinstaller

echo "    --> Cleaning up"
rm -rf build/ dist/ release/ electron/release/ electron/dist release-linux/ release-win/

echo "    --> Building specterd"
pyinstaller specterd.spec

echo "    --> Making us ready for building electron-app for linux"
cd electron
npm ci
node ./set-version $1 ../dist/specterd

echo "    --> building electron-app"
npm i
npm run dist -- --linux

cd ..

echo "    --> Making the release-zip"
mkdir release-linux
cd dist
cp -r ../../udev ./udev
echo "Don't forget to set up udev rules! Check out udev folder for instructions." > README.md
zip -r ../release-linux/specterd-"$1"-"$(uname -m)"-linux-gnu.zip specterd udev README.md

cp ../electron/dist/Specter-* ./
tar -czvf ../release-linux/specter_desktop-"$1"-"$(uname -m)"-linux-gnu.tar.gz Specter-* udev README.md

echo "    --> Cleaning up"
cd ..
rm -rf dist
mkdir dist
cd dist
echo "    --> Downloading the windows-version of specterd for version $1"
wget --progress=dot -e dotbytes=10M https://github.com/${CI_PROJECT_ROOT_NAMESPACE}/specter-desktop/releases/download/$1/specterd-$1-win64.zip -O ./specterd.zip
unzip specterd.zip
cd ../electron
rm -rf dist/
echo "    --> Making us ready for building electron-app for windows"
npm ci
node ./set-version $1 ../dist/specterd.exe
npm run dist -- --win
cd ..

mkdir release-win
cp electron/dist/Specter\ Setup\ *.exe release-win/Specter-Setup-$1.exe

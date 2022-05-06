#!/usr/bin/env bash

set -e

# debug:
set -x

source build-common.sh

# pass version number as an argument 
echo "    --> This build got triggered for version $1"

echo $1 > version.txt

specify_app_name


install_build_requirements

cleanup

building_app

cd electron

prepare_npm

echo "    --> calculate the hash of the binary for download"
if [[ "$2" == 'make-hash' ]]
then
    node ./set-version $1 ../dist/${specterd_filename}
else
    node ./set-version $1
fi

echo "        Hash in version -data.json $(cat ./version-data.json | jq -r '.sha256')"
echo "        Hash of file $(sha256sum ../dist/${specterd_filename} )"

building_electron_app

cd ..

echo "    --> Making the release-zip"
mkdir release
cd dist
cp -r ../../udev ./udev
echo "Don't forget to set up udev rules! Check out udev folder for instructions." > README.md
zip -r ../release/${specterd_filename}-"$1"-"$(uname -m)"-linux-gnu.zip ${specterd_filename} udev README.md
echo $app_name
cp ../electron/dist/${app_name^}-* ./
tar -czvf ../release/${pkg_filename}-"$1"-"$(uname -m)"-linux-gnu.tar.gz ${app_name^}-* udev README.md

cd ..

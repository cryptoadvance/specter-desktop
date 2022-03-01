#!/usr/bin/env bash

set -e

# pass version number as an argument 
echo "    --> This build got triggered for version $1"

echo $1 > version.txt

if [ -z "$app_name" ]; then
  # activate virtualenv. This is e.g. not needed in CI
    specterd_filename=specterd
    specterimg_filename=Specter
    pkg_filename=specter_desktop
else
    specterd_filename=${app_name}d
    specterimg_filename=${app_name^}
    pkg_filename=${app_name}
    
fi

echo "    --> Installing (build)-requirements"
pip3 install -r requirements.txt --require-hashes
cd ..
# Order is relevant here. If you flip the followng lines, the hiddenimports for services won't work anymore
python3 setup.py install
pip3 install -e .
cd pyinstaller

echo "    --> Cleaning up"
rm -rf build/ dist/ release/ electron/release/ electron/dist

echo "    --> Building ${specterd_filename}"
specterd_filename=${specterd_filename} pyinstaller specterd.spec

echo "    --> Making us ready for building electron-app for linux"
cd electron
npm ci

# calculate the hash of the binary for download
if [[ "$2" == 'make-hash' ]]
then
    node ./set-version $1 ../dist/${specterd_filename}
else
    node ./set-version $1
fi

echo "    --> building electron-app"
npm i
npm run dist

cd ..

echo "    --> Making the release-zip"
mkdir release
cd dist
cp -r ../../udev ./udev
echo "Don't forget to set up udev rules! Check out udev folder for instructions." > README.md
zip -r ../release/${specterd_filename}-"$1"-"$(uname -m)"-linux-gnu.zip ${specterd_filename} udev README.md

cp ../electron/dist/Specter-* ./
tar -czvf ../release/specter_desktop-"$1"-"$(uname -m)"-linux-gnu.tar.gz Specter-* udev README.md

cd ..

#!/usr/bin/env bash

# pass version number as an argument 

pip install -e ..
pip install -r requirements.txt
rm -rf build/ dist/ release/
pyinstaller specter_desktop.spec
pyinstaller specterd.spec

mkdir release

mkdir release/specter_desktop-$1-`arch`-linux-gnu
cp dist/Specter release/specter_desktop-$1-`arch`-linux-gnu/
cp -r ../udev release/specter_desktop-$1-`arch`-linux-gnu/udev
tar -czvf release/specter_desktop-$1-`arch`-linux-gnu.tar.gz release/specter_desktop-$1-`arch`-linux-gnu

mkdir release/specterd-$1-`arch`-linux-gnu
cp dist/specterd release/specterd-$1-`arch`-linux-gnu/
cp -r ../udev release/specterd-$1-`arch`-linux-gnu/udev
tar -czvf release/specterd-$1-`arch`-linux-gnu.tar.gz release/specterd-$1-`arch`-linux-gnu

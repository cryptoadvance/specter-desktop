@ECHO OFF
echo %1 > version.txt
pip install -r requirements.txt  --require-hashes
pip install -e ..
rmdir /s /q .\dist\
rmdir /s /q .\build\
rmdir /s /q .\release\
pyinstaller.exe specter_desktop.spec
pyinstaller.exe specterd.spec

mkdir release

echo We've built everything we could, now zip specterd and run inno-setup for specter-desktop

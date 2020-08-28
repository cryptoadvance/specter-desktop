@ECHO OFF
pip install -e ..
pip install -r requirements.txt
rmdir /s /q .\dist\
rmdir /s /q .\build\
rmdir /s /q .\release\
rmdir /s /q .\specterd\
pyinstaller.exe specterd_onedir.spec
move dist\specterd specterd
pyinstaller.exe specter_desktop.spec
pyinstaller.exe specterd.spec

mkdir release

echo We've built everything we could, now zip specterd and run inno-setup for specter-desktop
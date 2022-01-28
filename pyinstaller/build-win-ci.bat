@ECHO OFF
echo %1% > version.txt
pip3 install -r requirements.txt  --require-hashes
cd ..
Rem Order is relevant here. If you flip the followng lines, the hiddenimports for services won't work anymore
python3 setup.py install
pip3 install -e .
cd pyinstaller

rmdir /s /q .\dist\
rmdir /s /q .\build\
rmdir /s /q .\release\
rmdir /s /q .\electron\dist\
pyinstaller.exe specterd.spec

mkdir release

powershell Compress-Archive -Path dist\specterd.exe release\specterd-%1%-win64.zip

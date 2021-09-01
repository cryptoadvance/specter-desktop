@ECHO OFF
echo %1% > version.txt
pip3 install -r requirements.txt  --require-hashes
pip3 install -e ..
cd ..
python3 setup.py install
cd pyinstaller
rmdir /s /q .\dist\
rmdir /s /q .\build\
rmdir /s /q .\release\
rmdir /s /q .\electron\dist\
pyinstaller.exe specterd.spec
cd electron
call npm ci
if "%2%"=="make-hash" (
    call node ./set-version "%1%" "../dist/specterd.exe"
) else (
    node ./set-version "%1%"
)
call npm i
call npm run dist
cd ..


mkdir release
SET EXE_PATH="electron\dist\Specter Setup *.exe"
SET EXE_RELEASE_PATH="release\Specter Setup %1%.exe"
echo f | xcopy /s/y %EXE_PATH%  %EXE_RELEASE_PATH%

powershell Compress-Archive -Path dist\specterd.exe release\specterd-%1%-win64.zip

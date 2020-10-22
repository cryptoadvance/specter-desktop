@ECHO OFF
echo %1% > version.txt
pip install -r requirements.txt  --require-hashes
pip install -e ..
rmdir /s /q .\dist\
rmdir /s /q .\build\
rmdir /s /q .\release\
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
SET EXE_PATH="electron\dist\Specter Setup %1%.exe"
SET EXE_RELEASE_PATH="release\Specter Setup %1%.exe"
echo f | xcopy /s/y %EXE_PATH%  %EXE_RELEASE_PATH%

SET SPECTERD_PATH="dist\specterd.exe"
SET SPECTERD_RELEASE_PATH="release\specterd.exe"
echo f | xcopy /s/y %SPECTERD_PATH%  %SPECTERD_RELEASE_PATH%

echo We've built everything we could, now zip specterd and run inno-setup for specter-desktop

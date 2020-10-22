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
if (%2%=='make-hash') (
    call node ./set-version %1% ../specterd.exe
) else (
    node ./set-version %1%
)
call npm i
call npm run dist


mkdir release

echo We've built everything we could, now zip specterd and run inno-setup for specter-desktop

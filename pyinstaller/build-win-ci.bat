@ECHO OFF

python -V
pip3 install virtualenv
echo "    --> cleaning up"
rmdir /s /q .\release\
rmdir /s /q .\dist
rmdir /s /q .buildenv
echo "    --> Creating virtualenv"
virtualenv --python=python3 .buildenv
echo "    --> Activating virtualenv"
call .\.buildenv\Scripts\activate

echo "    --> Installing test-requirement"
pip3 install -e ".[test]"

echo "    --> Setting version in setup.py"
python .\utils\release-helper.py set_setup_py_version  %1%


echo "    --> Building pypi package"
python setup.py sdist bdist_wheel

echo "    --> Installing pypi package"
python .\utils\release-helper.py install_wheel %1%

pip3 install -r pyinstaller/test_requirements.txt
cd pyinstaller

Rem This file gets further packaged up with the pyinstaller and will help specter to figure out which version it's running on
echo %1% > version.txt
echo "    --> installing pyinstaller requirements"
pip3 install -r requirements.txt  --require-hashes

rmdir /s /q .\dist\
rmdir /s /q .\build\
rmdir /s /q .\release\
rmdir /s /q .\electron\dist\
pyinstaller.exe specterd.spec

mkdir release

powershell Compress-Archive -Path dist\specterd.exe release\specterd-%1%-win64.zip

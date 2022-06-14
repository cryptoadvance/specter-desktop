#!/bin/bash


pip3 install virtualenv
virtualenv --python=python3 .env
source .env/bin/activate
pip3 install -r requirements.txt --require-hashes
pip3 install -e .
python3 setup.py install # also compiles the babel translation-files


pip3 install -r test_requirements.txt
./tests/install_noded.sh --bitcoin binary
./tests/install_noded.sh --elements binary


export PATH=./tests/elements/bin/:./tests/bitcoin/bin/:$PATH

rm -Rf ./cypress/videos ./cypress/screenshots

./utils/test-cypress.sh run
pytest


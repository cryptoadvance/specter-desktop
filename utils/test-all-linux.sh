#!/bin/bash


pip3 install virtualenv
virtualenv --python=python3 .env
source .env/bin/activate
# removing modules related to cryptoadvance is faster than doing rm -rf .env
pip3 freeze | grep ^cryptoadvance | xargs pip uninstall -y   # the ^ means the line has to start with the search word
pip3 freeze | grep ^specterext | xargs pip uninstall -y    # the ^ means the line has to start with the search word
pip3 install -r requirements.txt --require-hashes
pip3 install -e . # this does not compile the babel translation-files


pip3 install -e ".[test]"
./tests/install_noded.sh --bitcoin binary
./tests/install_noded.sh --elements binary


export PATH=./tests/elements/bin/:./tests/bitcoin/bin/:$PATH

rm -Rf ./cypress/videos ./cypress/screenshots

./utils/test-cypress.sh run
pytest


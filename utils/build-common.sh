#!/usr/bin/env bash

# All functions in here are responsible to change directory
# from the project root to wherever they want
# They need to change back to project-root when they finish


function create_virtualenv_for_pyinstaller {
    echo "    --> Creating new virtualsenv"
    if [ -d .buildenv ]; then
        echo "        But first Delete it ..."
        rm -rf .buildenv
    fi
    virtualenv --python=python3.10 .buildenv
    source .buildenv/bin/activate
    pip3 install -e ".[test]"
}

function build_pypi_pckgs_and_install {
    echo "    --> Build pip3-package"
    rm -rf dist
    if ! git diff --quiet setup.py; then
        echo "ERROR: setup.py is dirty, can't reasonably build"
        exit 1
    fi
    if [[ "$OSTYPE" == "darwin"* ]]; then
        SML_ADD="\"\""
    fi
    pip3 install build==0.10.0
    python3 -m build
    pip3 install ./dist/cryptoadvance.specter-*.whl
}

function configure {
    echo "    --> Configure some variables"
    if [ -z "$app_name" ]; then
    # activate virtualenv. This is e.g. not needed in CI
        app_name=specter
        specterd_filename=specterd
        specterimg_filename=Specter
        pkg_filename=specter_desktop
    else
        specterd_filename=${app_name}d # usually "specterd"
        specterimg_filename=${app_name^} # usually "Specter"
        pkg_filename=${app_name}
    fi
    
    export ARCH=$(node -e "console.log(process.arch)")
    export dist_mac_folder_name=mac-universal
    export CI_COMMIT_TAG=$version
    export CI_PROJECT_ROOT_NAMESPACE=$(node -e "const downloadloc = require('./pyinstaller/electron/downloadloc');console.log(downloadloc.orgName())")

    echo specterd_filename=${specterd_filename}
    echo specterimg_filename=${specterimg_filename}
    echo pkg_filename=${pkg_filename}
    echo ARCH=$ARCH
    echo dist_mac_folder_name=$dist_mac_folder_name
    echo CI_COMMIT_TAG=$CI_COMMIT_TAG
    echo CI_PROJECT_ROOT_NAMESPACE=$CI_PROJECT_ROOT_NAMESPACE

}


function install_build_requirements {

    echo "    --> Installing pyinstaller build-requirements"
    cd pyinstaller
    pip3 install -r requirements.txt --require-hashes > /dev/null

    cd ..
}

function cleanup {
    echo "    --> Cleaning up"
    cd pyinstaller
    rm -rf build/ dist/ release/ electron/release/ electron/dist
    rm *.dmg || true
    cd ..
}

function building_app {
    echo "    --> Building ${specterd_filename}"
    cd pyinstaller
    specterd_filename=${specterd_filename} pyinstaller specterd.spec > /dev/null
    cd ..
}

function prepare_npm {
    cd pyinstaller/electron
    echo "    --> Making us ready for building electron-app"
    npm ci
    cd ../..
}

function make_hash_if_necessary {
    cd pyinstaller/electron
    echo "    --> calculate the hash of the binary for download"
    if [[ "$1" = "win" ]]; then
        specterd_plt_filename=../dist/${specterd_filename}.exe
    else
        specterd_plt_filename=../dist/${specterd_filename}
    fi
    if [[ "$make_hash" == 'True' ]]
    then
        node ./set-version $version ${specterd_plt_filename}
    else
        node ./set-version $version
    fi
    echo "        Hash in version -data.json $(cat ./version-data.json | jq -r '.sha256')"
    echo "        Hash of file $(sha256sum ${specterd_plt_filename} )"
    cd ../..
}

function building_electron_app {
    # https://www.electron.build/
    # Prerequisites:
    # * A developer Certificate (in the System keychain)
    # * private and public key in the login-keychain
    # * The cert needs to be referenced in pyinstaller/electron/package.json -> build.mac.identity


    platform="-- --${1}" # either linux or win (maxOS is empty)
    cd pyinstaller/electron
    echo "    --> building electron-app"
    echo "    --> Copying over resources"
    cp -R ../../src/cryptoadvance/specter/static/fonts ../../src/cryptoadvance/specter/static/output.css ../../src/cryptoadvance/specter/static/typography.css . 
    npm i
    npm run dist ${platform}
    cd ../..
}

function make_release_zip {
    echo "    --> Making the release-zip"
    
}

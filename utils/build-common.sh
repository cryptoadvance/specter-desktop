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
    virtualenv --python=python3 .buildenv
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

function specify_app_name {
    echo "    --> Specify app_name"
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

    echo specterd_filename=${specterd_filename}
    echo specterimg_filename=${specterimg_filename}
    echo pkg_filename=${pkg_filename}
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
    platform="-- --${1}" # either linux or win (maxOS is empty)
    cd pyinstaller/electron
    echo "    --> building electron-app"
    echo "    --> Copying over resources"
    cp -R ../../src/cryptoadvance/specter/static/fonts ../../src/cryptoadvance/specter/static/output.css ../../src/cryptoadvance/specter/static/typography.css . 
    npm i
    npm run dist ${platform}
    cd ../..
}

function macos_code_sign {
    # This creates a ZIP archive from the app package (using the ditto command).
    # This ZIP archive is then used to upload the app to the Apple notarization service.
    # After the app has been uploaded to the Apple servers and notarized, the ZIP archive is not used again.
    # The function uses the xcrun stapler command to attach the notarization result to the app, and then exits.

    # docs:
    # https://help.apple.com/itc/apploader/#/apdATD1E53-D1E1A1303-D1E53A1126
    # https://keith.github.io/xcode-man-pages/altool.1.html
    cd pyinstaller/electron
    echo '    --> Attempting to code sign...'
    echo '        executing: ditto -c -k --keepParent "dist/mac/${specterimg_filename}.app" dist/${specterimg_filename}.zip'
    ditto -c -k --keepParent "dist/mac/${specterimg_filename}.app" dist/${specterimg_filename}.zip
    # upload
    echo '        uploading ... '
    echo '        executing: xcrun altool --notarize-app -t osx -f dist/${specterimg_filename}.zip --primary-bundle-id "solutions.specter.desktop" -u "${mail}" --password "@keychain:AC_PASSWORD" --output-format json'
    output_json=$(xcrun altool --notarize-app -t osx -f dist/${specterimg_filename}.zip --primary-bundle-id "solutions.specter.desktop" -u "${mail}" --password "@keychain:AC_PASSWORD" --output-format json)
    echo "JSON-Output:"
    # parsing the requestuuid which we'll need to track progress
    requestuuid=$(echo $output_json | jq -r '."notarization-upload".RequestUUID')
    mkdir -p signing_logs
    i=1
    while [ $i -le 6 ] ; do
        echo "        check result in minute $i ..."
        sign_result_json=$(xcrun altool --notarization-info $requestuuid -u "${mail}" --password "@keychain:AC_PASSWORD" --output-format json)
        timestamp=$(date +"%Y%m%d-%H%M")
        # If it's not json-parseable
        if ! echo "$sign_result_json" | jq .; then
            echo $sign_result_json > ./signing_logs/${app_name}_${timestamp}_${requestuuid}.log
            echo "ERROR: track-json not parseable."
            echo "$sign_result_json"
            exit 1   
        fi
        # if it's no longer in progress
        status=$(echo "$sign_result_json" | jq -e -r '.["notarization-info"].Status')
        if [ "$status" != "in progress" ]; then
            echo "        Finished code sign with status $status"
            echo $sign_result_json | jq . > ./signing_logs/${app_name}_${timestamp}_${requestuuid}.log
            break
        fi
        i=$(( $i + 1 ))
        sleep 60
    done
    if [ "$status" != "success" ]; then
        echo "ERROR: status $status"
        echo $(echo $sign_result_json | jq .)
        echo
        exit 1
    fi
    # The stapler somehow "staples" the result of the notarisation in to your app
    # see e.g. https://stackoverflow.com/questions/58817903/how-to-download-notarized-files-from-apple
    xcrun stapler staple "dist/mac/${specterimg_filename}.app"
    cd ../..
}

function make_release_zip {
    echo "    --> Making the release-zip"
    
}

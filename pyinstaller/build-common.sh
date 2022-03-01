#!/usr/bin/env bash

function specify_app_name {
    if [ -z "$app_name" ]; then
    # activate virtualenv. This is e.g. not needed in CI
        app_name=specter
        specterd_filename=specterd
        specterimg_filename=Specter
        pkg_filename=specter_desktop
    else
        specterd_filename=${app_name}d
        specterimg_filename=${app_name^}
        pkg_filename=${app_name}
    fi

    echo specterd_filename=${specterd_filename}
    echo specterimg_filename=${specterimg_filename}
    echo pkg_filename=${pkg_filename}
}


function install_build_requirements {

    echo "    --> Installing (build)-requirements"
    pip3 install -r requirements.txt --require-hashes > /dev/null

    cd ..
    # Order is relevant here. If you flip the followng lines, the hiddenimports for services won't work anymore
    python3 setup.py install
    pip3 install -e .
    cd pyinstaller

}

function cleanup {
    echo "    --> Cleaning up"
    rm -rf build/ dist/ release/ electron/release/ electron/dist
    rm *.dmg || true
}

function building_app {
    echo "    --> Building ${specterd_filename}"
    specterd_filename=${specterd_filename} pyinstaller specterd.spec > /dev/null
}

function prepare_npm {
    echo "    --> Making us ready for building electron-app for MacOS"
    npm ci
}



function building_electron_app {
    echo "    --> building electron-app"
    npm i
    npm run dist
}

function macos_code_sign {
    echo '    --> Attempting to code sign...'
    ditto -c -k --keepParent "dist/mac/Specter.app" dist/Specter.zip
    output_json=$(xcrun altool --notarize-app -t osx -f dist/Specter.zip --primary-bundle-id "solutions.specter.desktop" -u "${mail}" --password "@keychain:AC_PASSWORD" --output-format json)
    echo "JSON-Output:"
    requestuuid=$(echo $output_json | jq -r '."notarization-upload".RequestUUID')
    sleep 180
    sign_result_json=$(xcrun altool --notarization-info $requestuuid -u "${mail}" --password "@keychain:AC_PASSWORD" --output-format json)
    mkdir -p signing_logs
    timestamp=$(date +"%Y%m%d-%H%M")
    echo $sign_result_json | jq . > ./signing_logs/${timestamp}_${requestuuid}.log
    xcrun stapler staple "dist/mac/Specter.app"
}

function make_release_zip {
    echo "    --> Making the release-zip"
    
}
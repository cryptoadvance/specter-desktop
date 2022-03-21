#!/usr/bin/env bash

function specify_app_name {
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

    echo "    --> Installing (build)-requirements"
    pip3 install -r requirements.txt --require-hashes > /dev/null

    cd ..
    # Order is relevant here. If you flip the followng lines, the hiddenimports for services won't work anymore
    python3 setup.py install > /dev/null
    pip3 install -e .  > /dev/null
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
    # docs:
    # https://help.apple.com/itc/apploader/#/apdATD1E53-D1E1A1303-D1E53A1126
    # https://keith.github.io/xcode-man-pages/altool.1.html
    echo '    --> Attempting to code sign...'
    ditto -c -k --keepParent "dist/mac/${specterimg_filename}.app" dist/${specterimg_filename}.zip
    # upload
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
}

function make_release_zip {
    echo "    --> Making the release-zip"
    
}
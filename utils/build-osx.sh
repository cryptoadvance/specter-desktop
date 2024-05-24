#!/usr/bin/env bash
set -e

# We start in the directory where this script is located
cd "$( dirname "${BASH_SOURCE[0]}" )/."
source build-common.sh
cd ..
# Now in project-root

# Overriding this function
function create_virtualenv_for_pyinstaller {
    # This currently assumes to be run with: Python 3.10.11
    # Important: pyinstaller needs a Python binary with shared library files
    # With pyenv, for example, you get this like so: env PYTHON_CONFIGURE_OPTS="--enable-shared" pyenv install 3.10.4
    # Use pyenv if available
    if command -v pyenv >/dev/null 2>&1; then
        ### This is usually in .zshrc, putting it in .bashrc didn't work ###
        ### 
        export PYENV_ROOT="$HOME/.pyenv"
        command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"
        eval "$(pyenv init -)"
        ### this needs the pyenv-virtualenv plugin. If you don't have it:
        ### git clone https://github.com/pyenv/pyenv-virtualenv.git $(pyenv root)/plugins/pyenv-virtualenv
        eval "$(pyenv virtualenv-init -)"
        ### ------------------------------------------------------------ ###
        PYTHON_VERSION=3.10.11
        export PYENV_VERSION=$PYTHON_VERSION
        echo "pyenv is available. Setting PYENV_VERSION to 3.10.4, using pyenv-virtualenv to create the buildenv..."
        # echo "    --> Deleting .buildenv"
        # pyenv uninstall -f .buildenv
        # rm -rf "$HOME/.pyenv/versions/$PYTHON_VERSION/envs/.buildenv"
        # pyenv virtualenv 3.10.4 .buildenv
        pyenv activate .buildenv
    else
        echo "pyenv is not available. Using system Python version."
        if [ -d .buildenv ]; then
          echo "    --> Deleting .buildenv"
          rm -rf .buildenv
        fi
        virtualenv .buildenv
        source .buildenv/bin/activate
    fi
    pip3 install -e ".[test]"
}

function macos_code_sign {
    # prerequisites for this:
    # in short:
    # * make sure you have a proper app-specific password on https://appleid.apple.com/account/manage
    # * collect some information via scrun altool --list-providers -u "<yourAppleID>"
    # * create profile via xcrun notarytool store-credentials --apple-id "<YourAppleID>" --password "app-specific-pw" --team-id "seeFromAbove"
    # * Call the profile: SpecterProfile
    # For details see:
    # * https://www.youtube.com/watch?v=2xJcMzoi0EI
    # * https://blog.dgunia.de/2022/09/01/switching-from-altool-to-notarytool/
    # * https://scriptingosx.com/2021/07/notarize-a-command-line-tool-with-notarytool/
    # This creates a ZIP archive from the app package (using the ditto command).
    # This ZIP archive is then used to upload the app to the Apple notarization service via xcrun notarytool (formerly xcrun altool)
    # After the app has been uploaded to the Apple servers and notarized, the ZIP archive is not used again.
    # The function uses the xcrun stapler command to attach the notarization result to the app, and then exits.

    # docs:
    # https://help.apple.com/itc/apploader/#/apdATD1E53-D1E1A1303-D1E53A1126
    # https://keith.github.io/xcode-man-pages/altool.1.html
    cd pyinstaller/electron
    echo '    --> Attempting to code sign...'
    echo '        executing: ditto -c -k --keepParent "dist/mac/${specterimg_filename}.app" dist/${specterimg_filename}.zip'

    ditto -c -k --keepParent "dist/${dist_mac_folder_name}/${specterimg_filename}.app" dist/${specterimg_filename}.zip
    # upload
    echo '        uploading ... '

    output_json=$(xcrun notarytool submit dist/${specterimg_filename}.zip  --apple-id "kneunert@gmail.com" --keychain-profile "SpecterProfile" --output-format json --wait )

    echo "Request ID: "
    # parsing the requestuuid which we'll need to track progress
    requestuuid=$(echo $output_json | jq -r '.id')
    status=$(echo $output_json | jq -r '.status')
    if [ "$status" = "Invalid" ]; then
        mkdir -p signing_logs
        echo "issues with notarisation"
        xcrun notarytool log ${requestuuid} --keychain-profile SpecterProfile | tee ./signing_logs/${app_name}_${timestamp}_${requestuuid}.log
        exit 1
    fi

    # The stapler somehow "staples" the result of the notarisation in to your app
    # see e.g. https://stackoverflow.com/questions/58817903/how-to-download-notarized-files-from-apple
    xcrun stapler staple "dist/${dist_mac_folder_name}/${specterimg_filename}.app"
    cd ../..
}


function sub_help {
    cat << EOF

### Quick overview
: <<'END_COMMENT'
    What do you need to sign the Specter app with Apple's notary service?
    - An Apple Developer account
    - You must create a signing certificate in your developer account, which will be used to sign your app.
    - This certificate must be stored in your keychain on your Mac.
    - When you create a signing certificate in your developer account, you will be asked to specify a password for the certificate.
    - You can store this password in the keychain, too, so that it - and thus the certificate - can be accessed automatically during the signing process. Like so:
        xcrun altool --store-password-in-keychain-item AC_PASSWORD -u '<your apple id>' -p apassword
    - As seen above, you need the the xcrun command line tool: This tool is also used to upload your app to the notary service and check the status of the notarization process.

In summary, to sign a macOS app with Apple's notary service, you need an Apple Developer account, a signing certificate, a password for your keychain, the app package to be signed, and the xcrun command line tool.
END_COMMENT

### Prerequisites
# brew install gmp # to prevent module 'embit.util' has no attribute 'ctypes_secp256k1'
# brew install jq
# npm install --global create-dmg

### Trouble shooting 
# If you have the common issue "errSecInternalComponent" while signing the code:
# https://medium.com/@ceyhunkeklik/how-to-fix-ios-application-code-signing-error-4818bd331327

# create-dmg issue? Note that there are 2 create-dmg scripts out there. We use:
# https://github.com/sindresorhus/create-dmg

The different "tasks" are now somehow separated from one another.
We have:
* make-hash is rather a flag for the electron-build to incorporate the hash of the specterd
* specterd will trigger the pyinstaller build of the specterd
* electron will build the electron-app
* sign will upload the electron-app to the Apple notary service and get it back notarized
* upload will upload all the binary artifacts to the github-release-page. This includes the creation of the hash-files
  and the gnupg signing

### Trouble shooting (Legacy)
# Currently, only MacOS Catalina is supported to build the dmg-file
# Therefore we expect xcode 12.1 (according to google)
# After installation of xcode: sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
# otherwise you get xcrun: error: unable to find utility "altool", not a developer tool or in PATH
# catalina might have a a too old version of bash. You need at least 4.0 or so
# 3.2 is too low definitely
# brew install bash

# Example-call:
./utils/build-osx.sh --debug --version v1.10.0-pre23 --appleid "Kim Neunert (FWV59JHV83)" --mail "kim@specter.solutions" make-hash specterd  electron sign upload
EOF
}

appleid=""

while [[ $# -gt 0 ]]
  do
  arg="$1"
  case $arg in
      "" | "-h" | "--help")
        sub_help
        exit 0
        shift
        ;;
      --debug)
        set -x
        DEBUG=true
        shift
        ;;
      --version)
        version=$2
        shift
        shift
        ;;
      --appleid)
        appleid=$2
        shift
        shift
        ;;
      --mail)
        mail=$2
        shift
        shift
        ;;
      specterd)
        build_specterd=True
        shift
        ;;
      make-hash)
        make_hash=True
        shift
        ;;
      electron)
        build_electron=True
        shift
        ;;
      sign)
        build_sign=True
        shift
        ;;
      package)
        build_package=True
        shift
        ;;
      upload)
        upload=True
        shift
        ;;        
      help)
        sub_help
        shift
        ;;
      *)
          shift
          sub_${arg} $@ && ret=0 || ret=$?
          if [ "$ret" = 127 ]; then
              echo "Error: '$arg' is not a known subcommand." >&2
              echo "       Run '$progname --help' for a list of known subcommands." >&2
              exit 1
          else
              exit $ret_value
          fi
          ;;
  esac
  done

echo "    --> This build got triggered for version $version"

echo $version > pyinstaller/version.txt

specify_app_name

if [[ "$build_specterd" = "True" ]]; then
  create_virtualenv_for_pyinstaller
  build_pypi_pckgs_and_install
  install_build_requirements
  cleanup
  building_app
fi

if [[ "$build_electron" = "True" ]]; then
  prepare_npm
  make_hash_if_necessary
  npm i
  if [[ "${appleid}" == '' ]]
  then
      echo "`jq '.build.mac.identity=null' package.json`" > package.json
  else
      echo "`jq '.build.mac.identity="'"${appleid}"'"' package.json`" > package.json
  fi
  building_electron_app
fi

if [[ "$build_sign" = "True" ]]; then
  dist_mac_folder_name=mac
  if [ "$(uname -m)" = "arm64" ]; then 
      dist_mac_folder_name=${dist_mac_folder_name}-arm64
  fi
  if [[ "$appleid" != '' ]]; then
    macos_code_sign
    create-dmg pyinstaller/electron/dist/mac/${specterimg_filename}.app --identity="Developer ID Application: ${appleid}" dist
    # create-dmg doesn't create the prepending "v" to the version
    node_comp_version=$(python3 -c "print('$version'[1:])")
    mv "dist/${specterimg_filename} ${node_comp_version}.dmg" release/${specterimg_filename}-${version}.dmg
  else
    echo "WARNING: Forgot to add the appleid ?!"
    exit 1
  fi
fi

if [[ "$build_package" = "True" ]]; then
  echo "    --> Making the release-zip"
  mkdir -p release
  rm -rf release/*
  export PLATFORM=$(uname -m)

  cd pyinstaller/dist # ./pyinstaller/dist
  if [[ -f ${specterd_filename} ]]; then
    zip ../../release/${specterd_filename}-${version}-osx_${PLATFORM}.zip ${specterd_filename}
  fi
  cd ../..
  if [[ -f ./release/${specterd_filename}-${version}-osx_${PLATFORM}.zip ]]; then
    sha256sum ./release/${specterd_filename}-${version}-osx_${PLATFORM}.zip
  fi
  if [[ -f ./release/${specterimg_filename}-${version}.dmg ]]; then
    sha256sum ./release/${specterimg_filename}-${version}.dmg
  fi
fi

if [ "$app_name" == "specter" ]; then
  echo "    --> gpg-signing the hashes and uploading"
  echo "--------------------------------------------------------------------------"
  
  echo "In order to upload these artifacts to github, we now do:"
  echo "We're keeping that here in case something fails on the last mile"
  echo "export CI_PROJECT_ROOT_NAMESPACE=cryptoadvance"
  echo "export CI_COMMIT_TAG=$version"
  echo "export GH_BIN_UPLOAD_PW=YourSecretHere"
  echo "export PLATFORM=$(uname -m)"
  echo "python3 ../utils/github.py upload ./release/specterd-${version}-osx.zip"
  echo "python3 ../utils/github.py upload ./release/Specter-${version}.dmg"
  echo "cd release"
  echo "sha256sum * > SHA256SUMS-macos_\$PLATFORM"
  echo "python3 ../../utils/github.py upload SHA256SUMS-macos_\$PLATFORM"
  echo "gpg --detach-sign --armor SHA256SUMS-macos_\$PLATFORM"
  echo "python3 ../../utils/github.py upload SHA256SUMS-macos_\$PLATFORM.asc"


  if [[ "$upload" = "True" ]]; then
    echo "    --> This build got triggered for version $version"
    . ../../specter_gh_upload.sh # A simple file looks like: export GH_BIN_UPLOAD_PW=...(GH token)
    export CI_COMMIT_TAG=$version
    if [[ -z "$CI_PROJECT_ROOT_NAMESPACE" ]]; then
      export CI_PROJECT_ROOT_NAMESPACE=cryptoadvance
    fi
    export PLATFORM=$(uname -m)
    export ARCH=$(node -e "console.log(process.arch")
    if [[ -f ./release/specterd-${version}-osx_${ARCH}.zip ]]; then
      python3 ./utils/github.py upload ./release/specterd-${version}-osx_${ARCH}.zip
    fi
    if [[ -f ./release/Specter-${version}.dmg ]]; then
      python3 ./utils/github.py upload ./release/Specter-${version}.dmg
    fi
    cd release
    sha256sum * > SHA256SUMS-macos_${ARCH}
    python3 ../utils/github.py upload SHA256SUMS-macos
    # The GPG comman below has a timeout. If that's reached, the script will interrupt. So let's make some noise
    say "Hello?! Your overlord is speaking! You're now allowed to sign the binary!"
    echo "Just in case you missed the timeout, those three last commands are missing:"
    echo "cd release"
    echo "gpg --detach-sign --armor SHA256SUMS-macos"
    echo "python3 ../utils/github.py upload SHA256SUMS-macos.asc"
    gpg --detach-sign --armor SHA256SUMS-macos__${ARCH}
    python3 ../utils/github.py upload SHA256SUMS-macos_${ARCH}.asc
  fi
fi


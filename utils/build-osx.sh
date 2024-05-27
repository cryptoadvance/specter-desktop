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
    #if command -v pyenv >/dev/null 2>&1; then
    if /bin/false ; then
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
        echo "    --> Deleting .buildenv"
        pyenv uninstall -f .buildenv
        rm -rf "$HOME/.pyenv/versions/$PYTHON_VERSION/envs/.buildenv"
        pyenv virtualenv 3.10.4 .buildenv
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

# Overriding this function to deal with the x86 special case
function make_hash_if_necessary {
    cd pyinstaller/electron
    echo "    --> calculate the hash of the binary for download"
    specterd_plt_filename=../dist/${specterd_filename}
    # early exit
    if [[ "$make_hash" != 'True' ]]; then
      node ./set-version $version
      return 0
    fi
    # Making the hash only makes sense on a arm arch
    if [[ "$ARCH" != "arm64" ]]; then
      echo "ERROR: make-hash should be only called on an arm64 machine on a mac"
      exit 1
    fi

    # We need to set-versions for two specterd, one arm and one intel. 
    # arm64 one
    node ./set-version $version ${specterd_plt_filename}
    # Download and check the intel one
    # this needs some env-vars to be set
    rm -rf signing_dir/*
    PYTHONPATH=../.. python3 -m utils.release-helper downloadgithub
    ret_code=$?
    if [ $ret_code -ne 0 ]; then
      echo "Downloading and verifying x64 specterd failed with exit code $ret_code"
      exit $ret_code
    fi
    if [[ ! -f ./signing_dir/specterd-${version}-osx_x64.zip ]]; then
      echo "Downloading and verifying x64 specterd failed as the file does not seem to be there"
      exit 1
    fi
    rm -f  /tmp/specterd
    unzip ./signing_dir/specterd-${version}-osx_x64.zip -d /tmp
    node ./set-version $version /tmp/specterd x64
    echo "        Hashes in version-data.json $(cat ./version-data.json | jq -r '.sha256')"
    echo "        Hash of file     $(sha256sum ${specterd_plt_filename} )"
    echo "        Hash of x64 file $(sha256sum /tmp/specterd )"
    cd ../..
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
    specterimg_filename_fqfn=dist/${dist_mac_folder_name}/${specterimg_filename}.app
    echo "        executing: ditto -c -k --keepParent "${specterimg_filename_fqfn}" dist/${specterimg_filename}.zip"

    ditto -c -k --keepParent "${specterimg_filename_fqfn}" dist/${specterimg_filename}.zip
    # upload
    echo '        uploading for notarisation ... '

    output_json=$(xcrun notarytool submit dist/${specterimg_filename}.zip  --apple-id "kneunert@gmail.com" --keychain-profile "SpecterProfile" --output-format json --wait )

    
    # parsing the requestuuid which we'll need to track progress
    requestuuid=$(echo $output_json | jq -r '.id')
    status=$(echo $output_json | jq -r '.status')
    echo "Request ID: $requestuuid"
    if [ "$status" = "Invalid" ]; then
        mkdir -p signing_logs
        echo "issues with notarisation"
        xcrun notarytool log ${requestuuid} --keychain-profile SpecterProfile | tee ./signing_logs/${app_name}_${timestamp}_${requestuuid}.log
        exit 1
    fi

    # The stapler somehow "staples" the result of the notarisation in to your app
    # see e.g. https://stackoverflow.com/questions/58817903/how-to-download-notarized-files-from-apple
    echo "    --> Staple the file dist/${dist_mac_folder_name}/${specterimg_filename}.app"
    xcrun stapler staple "dist/${dist_mac_folder_name}/${specterimg_filename}.app"
    echo '        Successfully Stapled the file'
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

configure

if [[ "$build_specterd" = "True" ]]; then
  create_virtualenv_for_pyinstaller
  build_pypi_pckgs_and_install
  install_build_requirements
  cleanup
  building_app
fi

if [[ "$make_hash" = "True" ]]; then
  make_hash_if_necessary
fi

if [[ "$build_electron" = "True" ]]; then
  prepare_npm
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
  # if [ "$(uname -m)" = "arm64" ]; then 
  #     dist_mac_folder_name=${dist_mac_folder_name}-arm64
  # fi
  if [[ "$appleid" != '' ]]; then
    macos_code_sign
  else
    echo "WARNING: Forgot to add the appleid ?!"
    exit 1
  fi
fi

if [[ "$build_package" = "True" ]]; then
  echo "    --> Preparing the release"
  mkdir -p release
  rm -rf release/*

  # The specterd-zipfile from specterd
  if [[ -f pyinstaller/dist/${specterd_filename} ]]; then
    echo "    --> Making the release-zip for specterd"
    pushd pyinstaller/dist # to not preserve folder structure
    zip ../../release/${specterd_filename}-${version}-osx_${ARCH}.zip ${specterd_filename}
    popd
  fi
  
  # The dmg image file from App
  if [[ -d pyinstaller/electron/dist/${dist_mac_folder_name}/${specterimg_filename}.app ]]; then
    rm -f pyinstaller/electron/dist/*.dmg
    echo "    --> Creating dmg"
    create-dmg pyinstaller/electron/dist/${dist_mac_folder_name}/${specterimg_filename}.app --identity="Developer ID Application: ${appleid}" pyinstaller/electron/dist
    # create-dmg doesn't create the prepending "v" to the version
    node_comp_version=$(python3 -c "print('$version'[1:])")
    mv "pyinstaller/electron/dist/${specterimg_filename} ${node_comp_version}.dmg" dist/${specterimg_filename}-${version}.dmg
    echo "    --> Copying img file dist/${specterimg_filename}-${version}.dmg"
    cp dist/${specterimg_filename}-${version}.dmg release/${specterimg_filename}-${version}.dmg
  else
    echo "WARNING: Skipping packaging for electron App"
    echo "No pyinstaller/electron/dist/${dist_mac_folder_name}/${specterimg_filename}.app has been found."
  fi
  
  file=./release/${specterd_filename}-${version}-osx_${ARCH}.zip
  if [[ -f $file ]]; then
    echo -n "    FYI : " 
    sha256sum $file
  fi
  file=./release/${specterimg_filename}-${version}.dmg
  if [[ -f $file ]]; then
    echo -n "    FIY : " 
    sha256sum $file
  fi
fi

if [ "$app_name" != "specter" ]; then
  # "early" exit
  if [[ "$upload" = "True" ]]; then
    echo "no upload for app_name $app_name"
    exit 1
  fi
  exit
fi
  
if [[ "$upload" = "True" ]]; then
  echo "    --> gpg-signing the hashes and uploading"
  . ../../specter_gh_upload.sh # A simple file looks like: export GH_BIN_UPLOAD_PW=...(GH token)
  export CI_COMMIT_TAG=$version
  if [[ -z "$CI_PROJECT_ROOT_NAMESPACE" ]]; then
    export got triggered for version $version=cryptoadvance
  fi
  echo "        This build: version: $version gh-project: $CI_PROJECT_ROOT_NAMESPACE"

  specterd_zip_fqfn=./release/specterd-${version}-osx_${ARCH}.zip
  echo "        Checking for file $specterd_zip_fqfn"
  if [[ -f $specterd_zip_fqfn ]]; then
    python3 ./utils/github.py upload $specterd_zip_fqfn
  else
    echo "        WARNING: not uploading as it does not exist: $specterd_zip_fqfn"
  fi
  
  specter_dmg_fqfn=./release/Specter-${version}.dmg
  echo "        Checking for file $specter_dmg_fqfn"
  if [[ -f $specter_dmg_fqfn ]]; then
    python3 ./utils/github.py upload $specter_dmg_fqfn
    else
    echo "        WARNING: not uploading as it does not exist: $specter_dmg_fqfn"
  fi

  cd release
  # Maybe we have some SHA256SUMS files from other runs lying around. We don't want to shasum them
  rm -f SHA256SUMS*
  sha256sum * > SHA256SUMS-macos_${ARCH}
  python3 ../utils/github.py upload SHA256SUMS-macos_${ARCH}
  # The GPG comman below has a timeout. If that's reached, the script will interrupt. So let's make some noise
  say "Hello?! Your overlord is speaking! You're now allowed to sign the binary!"
  echo "Just in case you missed the timeout, those three last commands are missing:"
  echo "cd release"
  echo "gpg --detach-sign --armor SHA256SUMS-macos_${ARCH}"
  echo "python3 ../utils/github.py upload SHA256SUMS-macos_${ARCH}.asc"

  gpg --detach-sign --armor SHA256SUMS-macos_${ARCH}
  python3 ../utils/github.py upload SHA256SUMS-macos_${ARCH}.asc
fi


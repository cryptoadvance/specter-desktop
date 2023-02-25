#!/usr/bin/env bash
set -e

# We start in the directory where this script is located
cd "$( dirname "${BASH_SOURCE[0]}" )/."
source build-common.sh
cd ..
# Now in project-root

# Overriding this function
function create_virtualenv_for_pyinstaller {
    if [ -d .buildenv ]; then
        echo "    --> Deleting .buildenv"
        rm -rf .buildenv
    fi
    # linux:
    # virtualenv --python=python3 .buildenv
    # we do:
    virtualenv --python=/usr/local/bin/python3 .buildenv
    source .buildenv/bin/activate
    pip3 install -e ".[test]"
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
# npm install --global create-dmg

### Trouble shooting 
# Currently, only MacOS Catalina is supported to build the dmg-file
# Therefore we expect xcode 12.1 (according to google)
# After installation of xcode: sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
# otherwise you get xcrun: error: unable to find utility "altool", not a developer tool or in PATH
# catalina might have a a too old version of bash. You need at least 4.0 or so
# 3.2 is too low definitely
# brew install bash

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
  if [[ "$appleid" != '' ]]
  then
    macos_code_sign
  fi

  echo "    --> Making the release-zip"
  mkdir -p release
  rm -rf release/*

  create-dmg pyinstaller/electron/dist/mac/${specterimg_filename}.app --identity="Developer ID Application: ${appleid}" dist
  # create-dmg doesn't create the prepending "v" to the version
  node_comp_version=$(python3 -c "print('$version'[1:])")
  mv "dist/${specterimg_filename} ${node_comp_version}.dmg" release/${specterimg_filename}-${version}.dmg

  cd pyinstaller/dist # ./pyinstaller/dist
  zip ../../release/${specterd_filename}-${version}-osx.zip ${specterd_filename}
  cd ../..

  sha256sum ./release/${specterd_filename}-${version}-osx.zip
  sha256sum ./release/${specterimg_filename}-${version}.dmg
fi

if [ "$app_name" == "specter" ]; then
  echo "    --> gpg-signing the hashes and uploading"
  echo "--------------------------------------------------------------------------"
  
  echo "In order to upload these artifacts to github, we now do:"
  echo "We're keeping that here in case something fails on the last mile"
  echo "export CI_PROJECT_ROOT_NAMESPACE=cryptoadvance"
  echo "export CI_COMMIT_TAG=$version"
  echo "export GH_BIN_UPLOAD_PW=YourSecretHere"
  echo "python3 ../utils/github.py upload ./release/specterd-${version}-osx.zip"
  echo "python3 ../utils/github.py upload ./release/Specter-${version}.dmg"
  echo "cd release"
  echo "sha256sum * > SHA256SUMS-macos"
  echo "python3 ../../utils/github.py upload SHA256SUMS-macos"
  echo "gpg --detach-sign --armor SHA256SUMS-macos"
  echo "python3 ../../utils/github.py upload SHA256SUMS-macos.asc"


  if [[ "$upload" = "True" ]]; then
    echo "    --> This build got triggered for version $version"
    . ../../specter_gh_upload.sh
    export CI_COMMIT_TAG=$version
    if [[ -z "$CI_PROJECT_ROOT_NAMESPACE" ]]; then
      export CI_PROJECT_ROOT_NAMESPACE=cryptoadvance
    fi
    python3 ./utils/github.py upload ./release/specterd-${version}-osx.zip
    python3 ./utils/github.py upload ./release/Specter-${version}.dmg
    cd release
    sha256sum * > SHA256SUMS-macos
    python3 ../utils/github.py upload SHA256SUMS-macos
    # The GPG comman below has a timeout. If that's reached, the script will interrupt. So let's make some noise
    say "Du darfst nun das binary signieren. Hoerst Du mich? Du darfst jetzt nun das binary signieren!"
    say "Nochmal, Du darfst nun das binary signieren. Hoerst Du mich? Du darfst jetzt nun das binary signieren!"
    echo "Just in case you missed the timeout, those three last commands are missing:"
    echo "cd release"
    echo "gpg --detach-sign --armor SHA256SUMS-macos"
    echo "python3 ../utils/github.py upload SHA256SUMS-macos.asc"
    gpg --detach-sign --armor SHA256SUMS-macos
    python3 ../utils/github.py upload SHA256SUMS-macos.asc
  fi
fi


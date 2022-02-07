#!/usr/bin/env bash
set -e



function sub_help {
    cat << EOF
# possible prerequisites
# brew install gmp # to prevent module 'embit.util' has no attribute 'ctypes_secp256k1'
# npm install --global create-dmg

# Download into torbrowser:
# wget -P torbrowser https://archive.torproject.org/tor-package-archive/torbrowser/10.0.15/TorBrowser-10.0.15-osx64_en-US.dmg

# Currently, only MacOS Catalina is supported to build the dmg-file
# Therefore we expect xcode 12.1 (according to google)
# After installation of xcode: sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
# otherwise you get xcrun: error: unable to find utility "altool", not a developer tool or in PATH

# Fill the keychain with your password like this
# xcrun altool --store-password-in-keychain-item AC_PASSWORD -u '<your apple id>' -p apassword

# You need to participate in the Apple-Developer Program (Eur 99,- yearly fee)
# https://developer.apple.com/programs/enroll/ 

# Then you need to create a cert which you need to store in the keychain
# https://developer.apple.com/account/resources/certificates/list

# If you have the common issue "errSecInternalComponent" while signing the code:
# https://medium.com/@ceyhunkeklik/how-to-fix-ios-application-code-signing-error-4818bd331327

# create-dmg issue? Note that there are 2 create-dmg scripts out there. We use:
# https://github.com/sindresorhus/create-dmg

# Example-call:
# ./build-osx.sh --debug --version v1.7.0-pre1 --appleid "Kim Neunert (FWV59JHV83)" --mail "kim@specter.solutions" make-hash
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
      make-hash)
        make_hash=True
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

echo $version > version.txt

echo "    --> Installing (build)-requirements"
pip3 install -r requirements.txt --require-hashes

cd ..
# Order is relevant here. If you flip the followng lines, the hiddenimports for services won't work anymore
python3 setup.py install
pip3 install -e .
cd pyinstaller

echo "    --> Cleaning up"
rm -rf build/ dist/ release/ electron/release/ electron/dist
rm *.dmg || true

echo "    --> Building specterd"
pyinstaller specterd.spec --runtime-hook=rthooks/hook-pkgutil.py

echo "    --> Making us ready for building electron-app for MacOS"
cd electron
npm ci
if [[ "$make_hash" = 'True' ]]
then
    node ./set-version $version ../dist/specterd
else
    node ./set-version $version
fi
npm i
if [[ "${appleid}" == '' ]]
then
    echo "`jq '.build.mac.identity=null' package.json`" > package.json
else
    echo "`jq '.build.mac.identity="'"${appleid}"'"' package.json`" > package.json
fi

echo "    --> building electron-app"
npm run dist

if [[ "$appleid" != '' ]]
then
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
fi

cd ..

echo "    --> Making the release-zip"
mkdir release

create-dmg 'electron/dist/mac/Specter.app' --identity="Developer ID Application: ${appleid}"
mv "Specter ${version:1}.dmg" release/SpecterDesktop-${version}.dmg

cd dist
zip ../release/specterd-${version}-osx.zip specterd
cd ..

sha256sum ./release/specterd-${version}-osx.zip
sha256sum ./release/SpecterDesktop-${version}.dmg

echo "--------------------------------------------------------------------------"
echo "In order to upload these artifacts to github, do:"
echo "export CI_PROJECT_ROOT_NAMESPACE=cryptoadvance"
echo "export CI_COMMIT_TAG=$version"
echo "export GH_BIN_UPLOAD_PW=YourSecretHere"
echo "python3 ../utils/github.py upload ./release/specterd-${version}-osx.zip"
echo "python3 ../utils/github.py upload ./release/SpecterDesktop-${version}.dmg"
echo "cd release"
echo "sha256sum * > SHA256SUMS-macos"
echo "python3 ../../utils/github.py upload SHA256SUMS-macos"
echo "gpg --detach-sign --armor SHA256SUMS-macos"
echo "python3 ../../utils/github.py upload SHA256SUMS-macos.asc"
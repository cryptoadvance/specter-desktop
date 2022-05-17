#!/usr/bin/env bash
set -e

# We start in the directory where this script is located
cd "$( dirname "${BASH_SOURCE[0]}" )/."
source build-common.sh
cd ..
# Now in project-root

function sub_help {
    cat << EOF

Building various components of specter-desktop
Usage: $build-unix [options] <subcommand> 

Options:
    --debug
      will set -x
    --version v1.2.3-pre4
      If you don't set the version, CI_COMMIT_TAG will determine the version

Subcommands:
    make-hash
      will make the hash for the electron-app. This hash will get checked after download
    
    specterd
      will build the pyinstaller's specterd binary (linux only)

    electron-linux
      will build the linux binary of the electron-app

    electron-win
      will build the win binary of the electron-app. The specterd.exe will get downloaded from
      github.com/\$CI_PROJECT_ROOT_NAMESPACE/specter-desktop...
      This need a wine-environment. See the docker-image electron-builder

Example-call:
./build-unix.sh --debug --version v1.7.0-pre1 make-hash specterd electron-linux
EOF
}

function create_release_zip_linux {
  echo "    --> Making the release-zip"
  # consists of specterd and Specter-version.AppImage
  mkdir -p release
  # first the specterd
  cd pyinstaller/dist
  cp -r ../../udev ./udev
  echo "Don't forget to set up udev rules! Check out udev folder for instructions." > README.md
  zip -r ../../release/${specterd_filename}-"$version"-"$(uname -m)"-linux-gnu.zip ${specterd_filename} udev README.md
  echo $app_name
  # now the AppImage
  cd ../electron/dist
  cp -r ../../../udev ./udev
  echo "Don't forget to set up udev rules! Check out udev folder for instructions." > README.md
  tar -czvf ../../../release/${pkg_filename}-"$version"-"$(uname -m)"-linux-gnu.tar.gz ${app_name^}-* udev README.md
  cd ../../..
}

function prepare_building_electron_app_win {
  cd pyinstaller/dist
  echo "    --> Downloading the windows-version of specterd for version $version"
  wget --progress=dot -e dotbytes=10M https://github.com/${CI_PROJECT_ROOT_NAMESPACE}/specter-desktop/releases/download/${version}/specterd-${version}-win64.zip -O ./specterd.zip
  unzip specterd.zip
  cd ../electron
  rm -rf dist/
  cd ../..
}

version=$CI_COMMIT_TAG

echo "    --> Assume gitlab-project: ${CI_PROJECT_ROOT_NAMESPACE}"

[ -z "${CI_PROJECT_ROOT_NAMESPACE:+x}" ]    && \
    echo "        Redefining CI_PROJECT_ROOT_NAMESPACE=cryptoadvance " && \
    export CI_PROJECT_ROOT_NAMESPACE=cryptoadvance

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
        if [ -n "$CI_COMMIT_TAG" ]; then
          if [ "$version" != "$CI_COMMIT_TAG" ]; then
            echo "ERROR: Cannot set version to something different than CI_COMMIT_TAG env-var if that var is set. "
            exit 1
          fi
        fi
        ;;
      specterd)
        build_specterd=True
        shift
        ;;
      make-hash)
        make_hash=True
        shift
        ;;
      electron-linux)
        build_electron_linux=True
        shift
        ;;
      electron-win)
        build_electron_win=True
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

if [[ "$version" = "" ]]; then
  echo "ERROR: version could not be determined (--version or CI_COMMIT_TAG)"
  exit 1
fi
echo "    --> This build got triggered for version $version"
# This file gets further packaged up with the pyinstaller and will help specter to figure out which version it's running on
echo $version > pyinstaller/version.txt

specify_app_name

if [[ "$build_specterd" = "True" ]]; then
  create_virtualenv_for_pyinstaller
  build_pypi_pckgs_and_install
  install_build_requirements
  cleanup
  building_app
fi

if [[ "$build_electron_linux" = "True" ]]; then
  prepare_npm
  make_hash_if_necessary
  building_electron_app linux
  create_release_zip_linux
fi

if [ "$build_electron_win" = "True" ]; then
  prepare_building_electron_app_win
  make_hash_if_necessary win
  building_electron_app win
  cp pyinstaller/electron/dist/Specter\ Setup\ *.exe release/Specter-Setup-$version.exe
fi



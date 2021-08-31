#!/bin/bash
# fail early
set -o pipefail

# change to the directory the script is located in
cd "$( dirname "${BASH_SOURCE[0]}" )/."

function checkout {
    node_impl=$1 # either bitcoin or elements

    # Clone bitcoind if it doesn't exist, or update it if it does
    # (copied from HWI)
    node_setup_needed=false
    if [ ! -d "./${node_impl}/.git" ]; then
        echo "    --> cloning $node_impl"
        if [ "$node_impl" = "elements" ]; then
            clone_url=https://github.com/ElementsProject/elements.git
        elif [ "$node_impl" = "bitcoin" ]; then
            clone_url=https://github.com/bitcoin/bitcoin.git
        else
            echo "unknown node_impl $node_impl"
            exit 1
        fi
        git clone $clone_url
        return 1
    fi
    return 0
}

function maybe_update {
    node_impl=$1 # either bitcoin or elements
    # Determine if we need to pull. From https://stackoverflow.com/a/3278427
    UPSTREAM=origin/master
    LOCAL=$(git describe --all | sed 's/heads\///' | sed 's/tags\///') # gives either a tag or "master" 
    if cat ../../pytest.ini | grep "addopts = --${node_impl}d-version" ; then
        # in this case, we use the expected version from the test also as the tag to be checked out
        # i admit that this is REALLY ugly. Happy for any recommendations to do that more easy
        PINNED=$(cat ../../pytest.ini | grep "addopts = " | cut -d'=' -f2 |  sed 's/--/+/g' | tr '+' '\n' | grep ${node_impl} |  cut -d' ' -f2)
        if [ "$node_impl" = "elements" ]; then
            # in the case of elements, the tags have a "elements-" prefix
            PINNED=$(echo "$PINNED" | sed 's/v//' | sed 's/^/elements-/')
        fi
    fi
    
    # the version in pytest.ini is (also) used to check the version via getnetworkinfo()["subversion"]
    # However, this might not be a valid git rev. So we need another way to specify the git-rev used
    # as we want to be able to test against specific commits
    if [ -f ../${node_impl}_gitrev_pinned ]; then
        PINNED=$(cat ../${node_impl}_gitrev_pinned)
    fi

    if [ -z $PINNED ]; then
        REMOTE=$(git rev-parse "$UPSTREAM")
        BASE=$(git merge-base @ "$UPSTREAM")
        if [ "$LOCAL" = "$REMOTE" ]; then
            echo "Up-to-date"
        elif [ "$LOCAL" = "$BASE" ]; then
            git pull
            git reset --hard origin/master
            return 1
        fi
    else
        if [ "$LOCAL" = "$PINNED" ]; then
            echo "    --> Pinned: $PINNED! Checkout not needed!"
        else
            echo "    --> Pinned: $PINNED! Checkout needed!"
            git fetch
            git checkout $PINNED
            return 1
        fi
    fi
    if [ -f ./tests/${node_impl}/src/${node_impl}d ]; then
        return 0
    else
        return 1
    fi
}

function calc_pytestinit_nodeimpl_version {

    # returns the version of $node_impl from pytest.ini from a line which looks like:
    # addopts = --bitcoind-version v0.21.1 --elementsd-version v0.20.99
    local node_impl=$1
    if cat ../pytest.ini | grep -q "addopts = --${node_impl}d-version" ; then
        # in this case, we use the expected version from the test also as the tag to be checked out
        # i admit that this is REALLY ugly. Happy for any recommendations to do that more easy
        PINNED=$(cat ../pytest.ini | grep "addopts = " | cut -d'=' -f2 |  sed 's/--/+/g' | tr '+' '\n' | grep ${node_impl} |  cut -d' ' -f2)
       
        if [ "$node_impl" = "elements" ]; then
            # in the case of elements, the tags have a "elements-" prefix
            PINNED=$(echo "$PINNED" | sed 's/v//' | sed 's/^/elements-/')
        fi
    fi
    echo $PINNED
}

function build_node_impl {
    node_impl=$1 # either bitcoin or elements
    nodeimpl_setup_needed=$2
    
    if [ "$nodeimpl_setup_needed" = 1 ] ; then
        echo "    --> Autogen & Configure necessary"
        # Build dependencies. This is super slow, but it is cached so it runs fairly quickly.
        cd contrib
        # This is hopefully fullfilles (via .travis.yml most relevantly)
        # sudo apt install make automake cmake curl g++-multilib libtool binutils-gold bsdmainutils pkg-config python3 patch
        echo "    --> Building db4"
        ./install_db4.sh $(pwd)
        echo "    --> Finishing db4"
        ls -l
        cd ..
        echo "    --> Setup needed. Starting autogen"
        ./autogen.sh
        echo "    --> Starting configure"
        export BDB_PREFIX="$(pwd)/contrib/db4"
        echo "        BDB_PREFIX=$BDB_PREFIX"
        # This is for reducing mem-footprint as for some reason cirrus fails even though it has 4GB Mem
        # CXXFLAGS="--param ggc-min-expand=1 --param ggc-min-heapsize=32768 -O2"
        
        if [ "$node_impl" = "elements" ]; then
            ./configure BDB_LIBS="-L${BDB_PREFIX}/lib -ldb_cxx-4.8" BDB_CFLAGS="-I${BDB_PREFIX}/include"
        elif [ "$node_impl" = "bitcoin" ]; then
            ./configure BDB_LIBS="-L${BDB_PREFIX}/lib -ldb_cxx-4.8" BDB_CFLAGS="-I${BDB_PREFIX}/include" CXXFLAGS="--param ggc-min-expand=1 --param ggc-min-heapsize=32768 -O2" --with-miniupnpc=no --without-gui --disable-zmq --disable-tests --disable-bench --with-libs=no --with-utils=no
        else
            echo "unknown node_impl $node_impl"
            exit 1
        fi
    else
        echo "    --> Skipping Autogen & Configure"
    fi
    export BDB_PREFIX="$(pwd)/contrib/db4"
    BDB_CFLAGS="-I${BDB_PREFIX}/include"
    # optimizing for speed would use the maximum threads available:
    #make -j$(nproc)
    # but we're optimizing for mem-allocation. 1 thread is quite slow, let's try 4 (we have 4GB and need to find the sweet-spot)
    make -j2
    cd ../.. #travis is sourcing this script
    echo "    --> Finished build $node_impl"


}

function sub_help {
    echo "This script will result in having bitcoind or elementsd binaries, either by binary download or via compilation"
    echo "Do one of these:"
    echo "$ ./install_node.sh --bitcoin compile"
    echo "$ ./install_node.sh --elements compile"
    echo "$ ./install_node.sh binary # only works for bitcoind currently, no binaries for elements"
    echo "For more context, see https://github.com/cryptoadvance/specter-desktop/blob/master/DEVELOPMENT.md#how-to-run-the-tests"
}

function check_compile_prerequisites {
    REQUIRED_PKGS="build-essential libtool autotools-dev automake pkg-config bsdmainutils python3 autoconf"
    REQUIRED_PKGS="$REQUIRED_PKGS libevent-dev libevent-dev libboost-dev libboost-system-dev libboost-filesystem-dev libboost-test-dev bc nodejs npm libgtk2.0-0 libgtk-3-0 libgbm-dev libnotify-dev libgconf-2-4 libnss3 libxss1 libasound2 libxtst6 xauth xvfb"
    for REQUIRED_PKG in $REQUIRED_PKGS; do
        PKG_OK=$(dpkg-query -W --showformat='${Status}\n' $REQUIRED_PKG|grep "install ok installed")
        echo Checking for $REQUIRED_PKG: $PKG_OK
        if [ "" = "$PKG_OK" ]; then
            echo "No $REQUIRED_PKG. Setting up $REQUIRED_PKG."
            echo "WARNING: THIS SHOULD NOT BE NECESSARY, PLEASE FIX!"
            apt-get --yes install $REQUIRED_PKG 
        fi
    done

}

function sub_compile {
    START=$(date +%s.%N)
    check_compile_prerequisites
    node_impl=$1
    echo "    --> install_node.sh Start $(date) (compiling for $node_impl)"
    echo "        checkout ..."
    checkout $node_impl
    cd $node_impl
    maybe_update $node_impl
    update=$?
    build_node_impl $node_impl $update
    echo "    --> Listing binaries"
    find tests/${node_impl}/src -maxdepth 1 -type f -executable -exec ls -ld {} \;
    END=$(date +%s.%N)
    DIFF=$(echo "$END - $START" | bc)
    echo "    --> install_node.sh End $(date) took $DIFF"
}

function sub_binary {
    if [ "$node_impl" = "elements" ]; then
        echo "    --> binary installation of elements not supported, exiting"
        exit 2
    fi
    echo "    --> install_noded.sh Start $(date) (binary)"
    START=$(date +%s.%N)
    # todo: Parametrize this
    version=$(calc_pytestinit_nodeimpl_version $node_impl)
    # remove the v-prefix
    version=$(echo $version | sed -e 's/v//')
    if [[ ! -f bitcoin-${version}-x86_64-linux-gnu.tar.gz ]]; then
        wget https://bitcoincore.org/bin/bitcoin-core-${version}/bitcoin-${version}-x86_64-linux-gnu.tar.gz
    fi
    tar -xzf bitcoin-${version}-x86_64-linux-gnu.tar.gz
    if [[ -d ./bitcoin ]]; then
        if [[ -d ./bitcoin/src ]]; then
            mv ./bitcoin ./bitcoin-src
        else
            rm -rf ./bitcoin
        fi
    fi
    ln -s ./bitcoin-${version} bitcoin
    echo "    --> Listing binaries"
    find ./bitcoin/bin -maxdepth 1 -type f -executable -exec ls -ld {} \;
    echo "    --> checking for bitcoind"
    test -x ./bitcoin/bin/bitcodind || (echo "not found" && exit 2)
    echo "    --> Finished installing bitcoind binary"
    END=$(date +%s.%N)
    DIFF=$(echo "$END - $START" | bc)
    echo "    --> install_noded.sh End $(date) took $DIFF"
}


function parse_and_execute() {
  if [[ $# = 0 ]]; then
    sub_default
    exit 0
  fi 

  while [[ $# -gt 0 ]]
  do
  arg="$1"
  case $arg in
      "" | "-h" | "--help")
        sub_help
        shift
        ;;
      --debug)
        set -x
        DEBUG=true
        shift
        ;;
      --bitcoin)
        node_impl=bitcoin
        shift
        ;;
      --elements)
        node_impl=elements
        shift
        ;;
      help)
        sub_help
        shift
        ;;
      compile)
        sub_compile $node_impl
        shift
        ;;
      binary)
        sub_binary
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
}

parse_and_execute $@
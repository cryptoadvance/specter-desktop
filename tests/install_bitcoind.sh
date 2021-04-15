#!/bin/bash


function sub_compile {


    echo "    --> install_bitcoind.sh Start $(date) (compiling)"
    START=$(date +%s.%N)
    # Clone bitcoind if it doesn't exist, or update it if it does
    # (copied from HWI)
    cd tests
    bitcoind_setup_needed=false
    if [ ! -d "./bitcoin/.git" ]; then
        echo "    --> cloning bitcoin"
        git clone https://github.com/bitcoin/bitcoin.git
        bitcoind_setup_needed=true
    fi

    cd bitcoin

    # Determine if we need to pull. From https://stackoverflow.com/a/3278427
    UPSTREAM=origin/master
    LOCAL=$(git describe --tags)
    if cat ../../pytest.ini | grep "addopts = --bitcoind-version" ; then
        PINNED=$(cat ../../pytest.ini | grep "addopts = --bitcoind-version" | cut -d' ' -f4)
    fi
    if [ -z $PINNED ]; then
        REMOTE=$(git rev-parse "$UPSTREAM")
        BASE=$(git merge-base @ "$UPSTREAM")
        if [ $LOCAL = $REMOTE ]; then
            echo "Up-to-date"
        elif [ $LOCAL = $BASE ]; then
            git pull
            git reset --hard origin/master
            bitcoind_setup_needed=true
        fi
    else
        if [ $LOCAL = $PINNED ]; then
            echo "    --> Pinned: $PINNED! Checkout not needed!"
        else
            echo "    --> Pinned: $PINNED! Checkout needed!"
            git fetch
            git checkout $PINNED || exit 1
            bitcoind_setup_needed=true
        fi
    fi



    # Build bitcoind. 
    if [ "$bitcoind_setup_needed" = "true" ] ; then
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
        # This is for reducing mem-footprint as for some reason cirrus fails even though it has 4GB Mem
        # CXXFLAGS="--param ggc-min-expand=1 --param ggc-min-heapsize=32768 -O2"
        ./configure BDB_LIBS="-L${BDB_PREFIX}/lib -ldb_cxx-4.8" BDB_CFLAGS="-I${BDB_PREFIX}/include" CXXFLAGS="--param ggc-min-expand=1 --param ggc-min-heapsize=32768 -O2" --with-miniupnpc=no --without-gui --disable-zmq --disable-tests --disable-bench --with-libs=no --with-utils=no
    fi
    make -j$(nproc) src/bitcoind
    cd ../.. #travis is sourcing this script
    echo "    --> Finished build bitcoind"
    END=$(date +%s.%N)
    DIFF=$(echo "$END - $START" | bc)
    echo "    --> install_bitcoind.sh End $(date) took $DIFF"
}

function sub_binary {
    echo "    --> install_bitcoind.sh Start $(date) (binary)"
    START=$(date +%s.%N)
    cd tests
    # todo: Parametrize this
    version=0.20.1
    wget https://bitcoincore.org/bin/bitcoin-core-${version}/bitcoin-${version}-x86_64-linux-gnu.tar.gz
    tar -xzf bitcoin-${version}-x86_64-linux-gnu.tar.gz
    if [[ -f ./bitcoin ]]; then
        echo "bitcoin -directory exists"
        return
    fi
    mv ./bitcoin-${version} bitcoin
    cd .. #cirrus is sourcing this script
    echo "    --> Finished installing bitcoind binary"
    END=$(date +%s.%N)
    DIFF=$(echo "$END - $START" | bc)
    echo "    --> install_bitcoind.sh End $(date) took $DIFF"
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
        sub_default
        shift
        ;;
      --debug)
        set -x
        DEBUG=true
        shift
        ;;
      compile)
        sub_compile
        shift
        ;;
      binary)
        sub_binary
        shift
        ;;
      *)
          shift
          sub_${arg} $@
          ret_value=$?
          if [ $ret_value = 127 ]; then
              echo "Error: '$arg' is not a known subcommand." >&2
              echo "       Run '$progname --help' for a list of known subcommands." >&2
              exit 1
          elif [ $ret_value = 0 ]; then
              exit 0
          else
              exit $ret_value
          fi
          ;;
  esac
  done
}
parse_and_execute $@
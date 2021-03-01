echo "    --> install_bitcoind.sh Start $(date)"
START=$(date +%s.%N)
# Clone bitcoind if it doesn't exist, or update it if it does
# (copied from HWI)
cd tests
bitcoind_setup_needed=false
if [ ! -d "./bitcoin/.git" ]; then
    echo "    --> cloning bitcoin"
    git clone https://github.com/bitcoin/bitcoin.git

    bitcoind_setup_needed=true
#else
    # do not unnecessarily fetch bitcoin as this affects the cache
    #echo "    --> fetching bitcoin"
    #git fetch
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
    ./configure BDB_LIBS="-L${BDB_PREFIX}/lib -ldb_cxx-4.8" BDB_CFLAGS="-I${BDB_PREFIX}/include" --with-miniupnpc=no --without-gui --disable-zmq --disable-tests --disable-bench --with-libs=no --with-utils=no
fi
make -j$(nproc) src/bitcoind
cd ../.. #travis is sourcing this script
echo "    --> Finished build bitcoind"
END=$(date +%s.%N)
DIFF=$(echo "$END - $START" | bc)
echo "    --> install_bitcoind.sh End $(date) took $DIFF"
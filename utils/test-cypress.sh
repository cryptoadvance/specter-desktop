#!/bin/bash
set -ex


function cleanup()
{
    if [ ! -z ${specter_pid+x} ]; then
        kill $specter_pid
    fi
    if [ ! -z ${bitcoind_pid+x} ]; then
        kill $bitcoind_pid
    fi
}
PORT=25444

trap cleanup EXIT


echo "Startting bitcoind in quiet mode ..."
python3 -m cryptoadvance.specter bitcoind --create-conn-json &
bitcoind_pid=$!

rm -rf ~/.specter


python3 -m cryptoadvance.specter server --port $PORT &
specter_pid=$!
$(npm bin)/wait-on http://localhost:${PORT}

$(npm bin)/cypress run



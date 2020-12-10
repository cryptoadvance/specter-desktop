#!/bin/bash
set -e

PORT=25444

# This needs to be the same than in config.py CypressTestConfig BTCD_REGTEST_DATA_DIR
# As we don't want to speculate here, we're injecting it via Env-var
export BTCD_REGTEST_DATA_DIR=/tmp/specter_cypress_btc_regtest_plain_datadir
# same with SPECTER_DATA_FOLDER
export SPECTER_DATA_FOLDER=~/.specter-cypress

. ./.env/bin/activate
function check_consistency {
    if ps | grep python; then
        echo "there is still a python-process running which is suspicious. Maybe wait a few more seconds"
        sleep 5
        ps | grep python && (echo "please investigate or kill " && exit 1)
    fi
}
check_consistency

function sub_default {
    cat << EOF
Usage: ./utils/test-cypress.sh [generic-options] <subcommand> [options]"
Doing stuff with cypress-tests according to <subcommand>"

Subcommands:"
    open [spec-file]    will open the cypress app."
    run  [spec-file]    will run the tests."
                        open and run take a spec-file optionally. If you add a spec-file, "
                        then automatically the corresponding snapshot is untarred before and," 
                        in the case of run, only the spec-file and all subsequent spec_files "
                        are executed."
    snapshot <spec_file>  will create a snapshot of the spec-file. It will create a tarball"
                        of the btc-dir and the specter-dir and store that file in the "
                        ./cypress/fixtures directory"

generic-options:
    --debug             Run as much stuff in debug as we can
    --docker            Run bitcoind in docker instead of directly
EOF
}

function start_bitcoind {
    if [ "$1" = "--reset" ]; then
        echo "--> Purging $BTCD_REGTEST_DATA_DIR"
        rm -rf $BTCD_REGTEST_DATA_DIR
    fi
    if [ "$1" = "--cleanuphard" ]; then
        addopts="--cleanuphard"
    fi
    if [ "$DOCKER" != "true" ]; then
        addopts="$addopts --nodocker"
    fi
    echo "--> Starting bitcoind with $addopts..."
    python3 -m cryptoadvance.specter $DEBUG bitcoind $addopts --create-conn-json --config CypressTestConfig &
    bitcoind_pid=$!
}

function stop_bitcoind {
    if [ ! -z ${bitcoind_pid+x} ]; then
        echo "--> Killing/Terminating bitcoindwrapper with PID $bitcoind_pid ..."
        kill $bitcoind_pid
        wait $bitcoind_pid
        unset bitcoind_pid
    fi
}

function start_specter {
    if [ "$1" = "--reset" ]; then
        echo "--> Purging $SPECTER_DATA_FOLDER"
        rm -rf $SPECTER_DATA_FOLDER
    fi
    echo "--> Starting specter ..."
    python3 -m cryptoadvance.specter $DEBUG server --config CypressTestConfig --debug > /dev/null &
    specter_pid=$!
    $(npm bin)/wait-on http://localhost:${PORT}
}

function stop_specter {
    if [ ! -z ${specter_pid+x} ]; then
        echo "--> Killing specter with PID $specter_pid ..."
        if [ -n "$DEBUG" ]; then
            pstree -p $specter_pid
        fi
        kill $specter_pid # kill -9 would orphane strange processes
        # We don't need to wait as that wastes time.
        unset specter_pid
    fi
}

function cleanup()
{
    stop_specter
    stop_bitcoind
}


trap cleanup EXIT


function restore_snapshot {
    spec_file=$1
    # Checking whether spec-files exists
    [ -f ./cypress/integration/${spec_file} ] || (echo "Spec-file $spec_file does not exist, these are the options:"; cat cypress.json | jq ".testFiles[]"; exit 1)
    snapshot_file=./cypress/fixtures/${spec_file}_btcdir.tar.gz
    [ -f ${snapshot_file} ] || (echo "Snapshot for Spec-file $spec_file does not exist, these are the options:"; ls -l ./cypress/fixtures; exit 1)
    ts_snapshot=$(stat --print="%X" ${snapshot_file})
    for file in $(./utils/calc_cypress_test_spec.py --delimiter " " $spec_file) 
    do 
        ts_spec_file=$(stat --print="%X" $file)
        if [ "$ts_spec_file" -gt "$ts_snapshot" ]; then
            echo "$file is newer ($ts_spec_file)than the snapshot for $spec_file ($ts_snapshot)"
            echo "please consider:"
            echo "./utils/test-cypress.sh snapshot $spec_file"
            exit 1
        fi
    done
    rm -rf /tmp/${BTCD_REGTEST_DATA_DIR}
    rm -rf $SPECTER_DATA_FOLDER
    echo "--> Unpacking ./cypress/fixtures/${spec_file}_btcdir.tar.gz ... "
    tar -xzf ./cypress/fixtures/${spec_file}_btcdir.tar.gz -C /tmp
    echo "--> Unpacking ./cypress/fixtures/${spec_file}_specterdir.tar.gz ... "
    tar -xzf ./cypress/fixtures/${spec_file}_specterdir.tar.gz -C ~
}

function sub_open {
    spec_file=$1
    if [ -n "${spec_file}" ]; then
        restore_snapshot ${spec_file}
        start_bitcoind --cleanuphard
        start_specter
    else
        start_bitcoind --reset
        start_specter --reset
    fi
    start_specter
    $(npm bin)/cypress open
}

function sub_run {
    spec_file=$1
    if [ -f ./cypress/integration/${spec_file} ]; then
        restore_snapshot ${spec_file}
        start_bitcoind --cleanuphard
        start_specter
        # Run $spec_file and all of the others coming later which come later!
        $(npm bin)/cypress run --spec $(./utils/calc_cypress_test_spec.py --run $spec_file)
    else 
        start_bitcoind --reset
        start_specter --reset
        $(npm bin)/cypress run
    fi
}

function sub_snapshot {
    spec_file=$1
    # We'll create a snapshot BEFORE this spec-file has been tested:
    if [ ! -f ./cypress/integration/$spec_file ]; then
        echo "ERROR: Use one of these arguments:"
        cat cypress.json | jq -r ".testFiles[]"
        exit 2
    fi
    start_bitcoind --reset
    start_specter --reset
    $(npm bin)/cypress run --spec $(./utils/calc_cypress_test_spec.py $spec_file)
    echo "--> stopping specter"
    stop_specter
    echo "--> stopping bitcoind gracefully ... won't take long ..."
    stop_bitcoind
    echo "--> Creating snapshot  $BTCD_REGTEST_DATA_DIR)"
    rm ./cypress/fixtures/${spec_file}_btcdir.tar.gz
    tar -czf ./cypress/fixtures/${spec_file}_btcdir.tar.gz -C /tmp $(basename $BTCD_REGTEST_DATA_DIR)
    echo "--> Creating snapshot of $SPECTER_DATA_FOLDER"
    rm ./cypress/fixtures/${spec_file}_specterdir.tar.gz
    tar -czf ./cypress/fixtures/${spec_file}_specterdir.tar.gz -C ~ $(basename $SPECTER_DATA_FOLDER)
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
          DEBUG=--debug
          shift
          ;;
      --docker)
          DOCKER=true
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

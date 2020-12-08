#!/bin/bash
set -e

PORT=25444

# This needs to be the same than in config.py CypressTestConfig BTCD_REGTEST_DATA_DIR
# As we don't want to speculate here, we're injecting it via Env-var
export BTCD_REGTEST_DATA_DIR=/tmp/specter_cypress_btc_regtest_plain_datadir

. ./.env/bin/activate

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
    echo "--> Starting bitcoind ..."
    if [ "$1" = "reset" ]; then
        if [ "$DOCKER" != "true" ]; then
            python3 -m cryptoadvance.specter $DEBUG bitcoind --reset --nodocker --config CypressTestConfig
        fi
    fi
    if [ "$1" = "--cleanuphard" ]; then
        addopts="--cleanuphard"
    fi
    if [ "$DOCKER" != "true" ]; then
        addopts="$addopts --nodocker"
    fi
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
    echo "--> Starting specter ..."
    python3 -m cryptoadvance.specter $DEBUG server --config CypressTestConfig --debug > /dev/null &
    specter_pid=$!
    $(npm bin)/wait-on http://localhost:${PORT}
}

function stop_specter {
    if [ ! -z ${specter_pid+x} ]; then
        echo "--> Killing specter with PID $specter_pid ..."
        kill $specter_pid
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
    [ -f ./cypress/integration/${spec_file} ] || (echo "Spec-file $spec_file does not exist, these are the options:"; cat cypress.json | jq ".testFiles[]"; exit 1)
    rm -rf /tmp/${BTCD_REGTEST_DATA_DIR}
    rm -rf ~/.specter-cypress
    echo "untaring ./cypress/fixtures/${spec_file}_btcdir.tar.gz ... "
    tar -xzf ./cypress/fixtures/${spec_file}_btcdir.tar.gz -C /tmp
    echo "untaring ./cypress/fixtures/${spec_file}_specterdir.tar.gz ... "
    tar -xzf ./cypress/fixtures/${spec_file}_specterdir.tar.gz -C ~
}

function sub_open {
    spec_file=$1
    if [ -n "${spec_file}" ]; then
        restore_snapshot ${spec_file}
        start_bitcoind --cleanuphard
    else
        start_bitcoind reset
    fi
    start_specter
    $(npm bin)/cypress open
}

function sub_run {
    spec_file=$1
    if [ -z ${spec_file} ]; then
        start_bitcoind reset
    else
        restore_snapshot ${spec_file}
        start_bitcoind --cleanuphard
    fi
    start_specter
    if [ -n ${spec_file} ]; then
        # Run $spec_file and all which come later!
        $(npm bin)/cypress run --spec $(./utils/calc_cypress_test_spec.py $spec_file --reverse)
    else
        $(npm bin)/cypress run
    fi
}

function sub_snapshot {
    spec_file=$1
    # We'll create a snapshot BEFORE this spec-file has been tested:
    if [ -z $spec_file ]; then
        echo "ERROR: Use one of these arguments:"
        cat cypress.json | jq -r ".testFiles[]"
        exit 2
    fi
    start_bitcoind
    start_specter
    $(npm bin)/cypress run --spec $(./utils/calc_cypress_test_spec.py $spec_file)
    echo "--> stopping specter"
    stop_specter
    echo "--> stopping bitcoind gracefully ... won't take long ..."
    stop_bitcoind
    echo "--> Creating snapshot  $BTCD_REGTEST_DATA_DIR)"
    tar -czf ./cypress/fixtures/${spec_file}_btcdir.tar.gz -C /tmp $(basename $BTCD_REGTEST_DATA_DIR)
    echo "--> Creating snapshot of ~/.specter-cypress"
    tar -czf ./cypress/fixtures/${spec_file}_specterdir.tar.gz -C ~ .specter-cypress
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

#!/bin/bash
set -e

PORT=25444
default_bitcoind_datadir=/tmp/specter_btcd_regtest_plain_datadir


. ./.env/bin/activate

function sub_default {
    echo "Usage: ./utils/test-cypress.sh <subcommand> [options]"
    echo "  Doing stuff with cypress-tests according to <subcommand>"
    echo ""
    echo "Subcommands:"
    echo "    open                  will open the cypress app."
    echo "    run                   will run the tests."
    echo "    snapshot <spec_file>  will create a snapshot of the spec-file. It will create a tarball"
    echo "                          of the btc-dir and the specter-dir and store that file in the "
    echo "                          ./cypress/fixtures directory"
    echo ""
    echo "open and run take a spec-file optionally. If you add a spec-file, then automatically the"
    echo "corresponding snapshot is untarred before and, in the case of run, only the spec-file and"
    echo "all subsequent spec_files are executed."
    echo ""
}

function start_bitcoind {
    echo "Startting bitcoind ..."
    if [ "$1" == "reset" ]; then
        if [ "$DOCKER" = "true" ]; then
            return
        else
            python3 -m cryptoadvance.specter bitcoind --reset --nodocker --config CypressTestConfig
        fi
    fi
    if [ "$DOCKER" != "true" ]; then
        addopts=--nodocker
    fi
    python3 -m cryptoadvance.specter bitcoind $addopts --create-conn-json --config CypressTestConfig &
    bitcoind_pid=$!
}

function stop_bitcoind {
    if [ ! -z ${bitcoind_pid+x} ]; then
        kill $bitcoind_pid
    fi
}

function start_specter {
    python3 -m cryptoadvance.specter server --config CypressTestConfig --debug &
    specter_pid=$!
    $(npm bin)/wait-on http://localhost:${PORT}
}

function stop_specter {
    if [ ! -z ${specter_pid+x} ]; then
        kill $specter_pid
    fi
}

function cleanup()
{
    stop_bitcoind
    stop_specter
}


trap cleanup EXIT


function restore_snapshot {
    spec_file=$1
    [ -f ./cypress/integration/${spec_file} ] || (echo "Spec-file $spec_file does not exist, these are the options:"; cat cypress.json | jq ".testFiles[]"; exit 1)
    rm -rf /tmp/${default_bitcoind_datadir}
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
        start_bitcoind
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
        start_bitcoind
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
        echo "we need one of these arguments:"
        cat cypress.json | jq -r ".testFiles[]"
        exit 2
    fi
    start_bitcoind
    start_specter
    $(npm bin)/cypress run --spec $(./utils/calc_cypress_test_spec.py $spec_file)
    stop_bitcoind
    stop_specter
    tar -czf ./cypress/fixtures/${spec_file}_btcdir.tar.gz -C /tmp specter_btcd_regtest_plain_datadir
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
          DEBUG=true
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

#!/bin/bash
set -e

PORT=25444

# This needs to be the same than in config.py CypressTestConfig BTCD_REGTEST_DATA_DIR
# As we don't want to speculate here, we're injecting it via Env-var
export BTCD_REGTEST_DATA_DIR=/tmp/specter_cypress_btc_regtest_plain_datadir
# same with SPECTER_DATA_FOLDER
export SPECTER_DATA_FOLDER=~/.specter-cypress
# We'll might change that on the "dev-function"
export SPECTER_CONFIG=CypressTestConfig

if [ -z "$VIRTUAL_ENV" ]; then
  # activate virtualenv. This is e.g. not needed in CI
  source ./.env/bin/activate
fi

function check_consistency {
  if ! npm version 2> /dev/null 1>&2 ; then
    echo "npm is not on the PATH. Please install node and bring on the PATH"
    exit 1
  fi
  if ps | grep python | grep -v grep ; then # the second grep might be necessary because MacOs has a non POSIX ps
      echo "there is still a python-process running which is suspicious. Maybe wait a few more seconds"
      sleep 5
      ps | grep python && (echo "please investigate or kill " && exit 1)
  fi
  $(npm bin)/cypress verify
}

check_consistency

function sub_default {
    cat << EOF
Usage: ./utils/test-cypress.sh [generic-options] <subcommand> [options]"
Doing stuff with cypress-tests according to <subcommand>"

Subcommands:
    open [spec-file]    will open the cypress app and maybe unpack the corresponding snapshot upfront
    dev [spec-file]     will run regtest+specter and maybe unpack the corresponding snapshot upfront 
    run  [spec-file]    will run the tests.
                        open and run take a spec-file optionally. If you add a spec-file, 
                        then automatically the corresponding snapshot is untarred before and,
                        in the case of run, only the spec-file and all subsequent spec_files 
                        are executed.
    snapshot <spec_file>  will create a snapshot of the spec-file. It will create a tarball
                        of the btc-dir and the specter-dir and store those files in the 
                        ./cypress/fixtures directory

generic-options:
    --debug             Run as much stuff in debug as we can
    --docker            Run bitcoind in docker instead of directly
EOF
}

function open() {
  unameOut="$(uname -s)"
  case "${unameOut}" in
      Linux*)
      sleep 2 # 2 more seconds on linux ;-)
        xdg-open $*
        ;;
      Darwin*)
        open $*
        ;;
      CYGWIN*)
        open $* # Not so sure about that, though
        ;;
      *)
        echo "UNKNOWN:${unameOut} , cannot open browser!"
        ;;
  esac
}

exit_if_macos() {
  if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Very sorry but this functionality is not yet ready for MacOS :-(."
    echo "If you can fix that, PRs are very much appreciated!"
    echo "it's basically the different behaviour of GNU-tools on Linux/MacOS."
    echo "first step to help is find the calls of \"exit_if_macos\" and deactivate it!"
    exit 2
  fi
}

function send_signal() {
  # use like send_signal <SIGNAL> <PID>
  # whereas SIGNAL is either SIGTERM or SIGKILL
  if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux wants no SIG-prefix'
    signal_name=$(echo $1 | sed -e 's/SIG//')
    kill -${1} $2
  elif [[ "$OSTYPE" == "darwin"* ]]; then
    # MacOS needs SIG-prefix
    kill -s $1 $2
  fi
}

function start_bitcoind {

  while [[ $# -gt 0 ]]; do
    arg="$1"
    case $arg in
      --reset)
        echo "--> Purging $BTCD_REGTEST_DATA_DIR"
        rm -rf $BTCD_REGTEST_DATA_DIR
        shift
        ;;
      --cleanuphard)
        addopts="--cleanuphard"
        shift
        ;;
      *)
        echo "unrecognized argument for start_bitcoind: $1 "
        exit 1
        shift
        ;;
    esac
  done

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
  python3 -m cryptoadvance.specter $DEBUG bitcoind $addopts --create-conn-json --config $SPECTER_CONFIG &
  bitcoind_pid=$!
  while ! [ -f ./btcd-conn.json ] ; do
      sleep 0.5
  done

}

function stop_bitcoind {
  if [ ! -z ${bitcoind_pid+x} ]; then
    echo "--> Killing/Terminating bitcoindwrapper with PID $bitcoind_pid ..."
    send_signal SIGTERM $bitcoind_pid
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
  python3 -m cryptoadvance.specter $DEBUG server --config $SPECTER_CONFIG --debug > /dev/null &
  specter_pid=$!
  $(npm bin)/wait-on http://localhost:${PORT}
}

function stop_specter {
  if [ ! -z ${specter_pid+x} ]; then
    echo "--> Terminating specter with PID $specter_pid ..."
    send_signal SIGTERM $specter_pid # kill -9 would orphane strange processes
    # We don't need to wait as that wastes time.
    unset specter_pid
  fi
}

function cleanup()
{
    stop_specter || :
    stop_bitcoind || :
}


trap cleanup EXIT


function restore_snapshot {
  spec_file=$1
  # Checking whether spec-files exists
  [ -f ./cypress/integration/${spec_file} ] || (echo "Spec-file $spec_file does not exist, these are the options:"; cat cypress.json | jq -r ".testFiles[]"; exit 1)
  snapshot_file=./cypress/fixtures/${spec_file}_btcdir.tar.gz
  if ! [ -f ${snapshot_file} ]; then
    echo "Snapshot for Spec-file $spec_file does not exist, these are the options:"
    ls ./cypress/fixtures -1 | sed -e 's/_btcdir.tar.gz//' -e 's/_specterdir.tar.gz//' | uniq
    echo "But maybe you want to create that snapshot like this:"
    echo "./utils/test-cypress.sh snapshot $spec_file"
    exit 1
  fi
  exit_if_macos
  ts_snapshot=$(stat --print="%X" ${snapshot_file})
  for file in $(./utils/calc_cypress_test_spec.py --delimiter " " $spec_file) 
  do 
    ts_spec_file=$(stat --print="%X" $file)
    if [ "$ts_spec_file" -gt "$ts_snapshot" ]; then
      echo "$file is newer ($ts_spec_file)than the snapshot for $spec_file ($ts_snapshot)"
      echo "please consider to create a new snapshot:"
      echo "./utils/test-cypress.sh snapshot $spec_file"
      exit 1
    fi
  done
  rm -rf ${BTCD_REGTEST_DATA_DIR}
  mkdir ${BTCD_REGTEST_DATA_DIR}
  rm -rf $SPECTER_DATA_FOLDER
  mkdir $SPECTER_DATA_FOLDER
  echo "--> Unpacking ./cypress/fixtures/${spec_file}_btcdir.tar.gz ... "
  tar -xzf ./cypress/fixtures/${spec_file}_btcdir.tar.gz -C ${BTCD_REGTEST_DATA_DIR} --strip-components=1
  echo "--> Unpacking ./cypress/fixtures/${spec_file}_specterdir.tar.gz ... "
  tar -xzf ./cypress/fixtures/${spec_file}_specterdir.tar.gz -C $SPECTER_DATA_FOLDER --strip-components=1
}

function sub_dev {
  spec_file=$1
  # Sad that we need to specify stuff here, which is usually specified in config.py
  
  # We could potentially do that on the original ~/.specter folder like this:
  #local SPECTER_DATA_FOLDER=~/.specter
  #local BTCD_REGTEST_DATA_DIR=/tmp/specter_btc_regtest_plain_datadir
  #local SPECTER_CONFIG=DevelopmentConfig
  #local PORT=25441
  
  if [ -n "${spec_file}" ]; then
    restore_snapshot ${spec_file}
    start_bitcoind --cleanuphard
    start_specter
  else
    start_bitcoind --reset
    start_specter --reset
  fi
  open http://localhost:${PORT}
  sleep infinity
}

function sub_open {
  spec_file=$1
  if [ -n "${spec_file}" ]; then
    restore_snapshot ${spec_file}
    start_bitcoind --cleanuphard --reset
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
    start_bitcoind --cleanuphard --reset
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
  rm ./cypress/fixtures/${spec_file}_btcdir.tar.gz 2> /dev/null 1>&2 || :
  tar -czf ./cypress/fixtures/${spec_file}_btcdir.tar.gz -C /tmp $(basename $BTCD_REGTEST_DATA_DIR)
  echo "--> Creating snapshot of $SPECTER_DATA_FOLDER"
  rm ./cypress/fixtures/${spec_file}_specterdir.tar.gz 2> /dev/null 1>&2 || :
  tar -czf ./cypress/fixtures/${spec_file}_specterdir.tar.gz -C ~ $(basename $SPECTER_DATA_FOLDER)
}

function sub_export-snapshot {
  rm -rf ~/.specter || :
  mkdir ~/.specter
  # mv ~/.specter-cypress ~/.specter
  tar -xzf cypress/fixtures/spec_node_configured.js_specterdir.tar.gz -C ~/.specter --strip-components=1
  rm -rf  /tmp/specter_btc_regtest_plain_datadir
  mkdir /tmp/specter_btc_regtest_plain_datadir
  tar -xzf cypress/fixtures/spec_node_configured.js_btcdir.tar.gz -C /tmp/specter_btc_regtest_plain_datadir --strip-components=1
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

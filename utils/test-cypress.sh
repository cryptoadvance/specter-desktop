#!/bin/bash
set -e

PORT=25444

# This needs to be the same than in config.py CypressTestConfig BTCD_REGTEST_DATA_DIR
# As we don't want to speculate here, we're injecting it via Env-var
export BTCD_REGTEST_DATA_DIR=/tmp/specter_cypress_btc_regtest_plain_datadir
# same with this
export ELMD_REGTEST_DATA_DIR=/tmp/specter_cypress_elm_regtest_plain_datadir
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
    echo "npm is not on the PATH. Please install node and bring it on the PATH."
    exit 1
  fi
  if ! ps | grep python | grep -q -v grep; then
    echo "There are no other Python processes running, good to go!"
  else 
    GREP_OUTPUT=$(ps | grep python | grep -v grep) 
    SPECTER_STR="cryptoadvance.specter server"
    while read -r line; do # https://unix.stackexchange.com/questions/9784/how-can-i-read-line-by-line-from-a-variable-in-bash
      if [[ "$line" == *"$SPECTER_STR"* ]]; then 
          echo "There is another Specter process running, this is fine."
      else
        echo "There is a suspicious Python process running. Maybe wait a few more seconds."
        sleep 5
        echo "Please investigate the following process and perhaps kill: $line"
        exit 1
      fi
    done <<< "$GREP_OUTPUT"
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
    snapshot [spec_file]  will create a snapshot of the spec-file. It will create a tarball
                          of the btc-/elm-dir and the specter-dir and store those files in the 
                          ./cypress/fixtures directory

generic-options:
    --debug             Run as much stuff in debug as we can
    --with-elements     In addition to bitcoind, also start elementsd
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



function start_node {
  addopts=""
  while [[ $# -gt 0 ]]; do
    arg="$1"
    case $arg in
      --bitcoin)
        node_impl=bitcoind
        node_impl_abbrev=btcd
        node_port=15443
        shift
        ;;
      --elements)
        node_impl=elementsd
        node_impl_abbrev=elmd
        node_port=8040
        shift
        ;;
      --reset)
        RESET=true
        shift
        ;;
      --cleanuphard)
        CLEANUPHARD=true
        shift
        ;;
      *)
        echo "unrecognized argument for start_node: $1 "
        exit 1
        shift
        ;;
    esac
  done

  if [ "$RESET" = "true" ]; then
    if [ "$node_impl" = "bitcoind" ]; then
      echo "--> Purging $BTCD_REGTEST_DATA_DIR"
      rm -rf $BTCD_REGTEST_DATA_DIR
    else
      echo "--> Purging $ELMD_REGTEST_DATA_DIR"
      rm -rf $ELMD_REGTEST_DATA_DIR
    fi
  fi
  if [ "$CLEANUPHARD" = "true" ]; then
      addopts="--cleanuphard"
  fi
  if [ "$node_impl" = "bitcoind" ]; then
    if [ "$BTCLOGSTDOUT" = "true" ]; then
      addopts="--log-stdout"
    fi
  else
    if [ "$ELMLOGSTDOUT" = "true" ]; then
      addopts="--log-stdout"
    fi
  fi
  echo "--> Starting $node_impl with $addopts ..."
  python3 -m cryptoadvance.specter $DEBUG $node_impl $addopts --no-mining --port $node_port --create-conn-json --config $SPECTER_CONFIG &
  if [ "$node_impl" = "bitcoind" ]; then
    bitcoind_pid=$!
  else
    elementsd_pid=$!
  fi

  echo "--> Waiting for Starting ${node_impl_abbrev}-conn.json to be created ..."
  while ! [ -f ./${node_impl_abbrev}-conn.json ] ; do
      sleep 0.5
  done
  echo "--> ${node_impl_abbrev}-conn.json created ..."

}

function start_bitcoind {
  start_node --bitcoin $*
}

function start_elementsd {
  if [ $USE_ELEMENTSD = true ]; then
    start_node --elements $*
  fi
}

function stop_bitcoind {
  if [ ! -z ${bitcoind_pid+x} ]; then
    echo "--> Killing/Terminating bitcoindwrapper with PID $bitcoind_pid ..."
    send_signal SIGTERM $bitcoind_pid
    wait $bitcoind_pid
    unset bitcoind_pid
  fi
}

function stop_elementsd {
  if [ ! -z ${elementsd_pid+x} ]; then
    echo "--> Killing/Terminating elementsdwrapper with PID $elementsd_pid ..."
    send_signal SIGTERM $elementsd_pid
    wait $elementsd_pid
    unset elementsd_pid
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
  # Simulate slower machines with uncommenting this (-l 10 means using 10% cpu):
  #cpulimit -p $specter_pid -l 10 -b
  echo "--> Waiting for specter ..."
  $(npm bin)/wait-on http://127.0.0.1:${PORT} && echo "--> Success"
  
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
    stop_elementsd || : 
}


trap cleanup EXIT


function restore_snapshot {
  spec_file=$1
  # Checking whether spec-files exists
  if ! [ -f ./cypress/integration/${spec_file} ]; then
    echo "Spec-file $spec_file does not exist, these are the options:"
    cat cypress.json | jq -r ".testFiles[]" 
    exit 1
  fi
  snapshot_file=./cypress/fixtures/${spec_file}_btcdir.tar.gz
  if ! [ -f ${snapshot_file} ]; then
    echo "Snapshot for Spec-file $spec_file does not exist, these are the options:"
    ls ./cypress/fixtures | awk '{ print $1 }' | sed -e 's/_btcdir.tar.gz//' -e 's/_specterdir.tar.gz//' | uniq # single line, awk for macos
    echo "But maybe you want to create that snapshot like this:"
    echo "./utils/test-cypress.sh snapshot $spec_file"
    exit 1
  fi
  if [ $(uname) = "Darwin" ]; then
	  ts_snapshot=$(stat -f "%m" ${snapshot_file})
  else
	  ts_snapshot=$(stat --print="%X" ${snapshot_file})
  fi
  for file in $(./utils/calc_cypress_test_spec.py --delimiter " " $spec_file) 
  do 
    if [ $(uname) = "Darwin" ]; then
      ts_spec_file=$(stat -f "%m" $file)
    else
      ts_spec_file=$(stat --print="%X" $file)
    fi
    if [ "$ts_spec_file" -gt "$ts_snapshot" ]; then
      echo "$file is newer ($ts_spec_file)than the snapshot for $spec_file ($ts_snapshot)"
      echo "please consider to create a new snapshot:"
      echo "./utils/test-cypress.sh snapshot $spec_file"
      exit 1
    fi
  done

  rm -rf ${BTCD_REGTEST_DATA_DIR}
  mkdir ${BTCD_REGTEST_DATA_DIR}
  echo "--> Unpacking ./cypress/fixtures/${spec_file}_btcdir.tar.gz ... into ${BTCD_REGTEST_DATA_DIR}"
  tar -xzf ./cypress/fixtures/${spec_file}_btcdir.tar.gz -C ${BTCD_REGTEST_DATA_DIR} --strip-components=1

  rm -rf ${ELMD_REGTEST_DATA_DIR}
  mkdir ${ELMD_REGTEST_DATA_DIR}
  echo "--> Unpacking ./cypress/fixtures/${spec_file}_elmdir.tar.gz into ${ELMD_REGTEST_DATA_DIR} ..."
  tar -xzf ./cypress/fixtures/${spec_file}_elmdir.tar.gz -C ${ELMD_REGTEST_DATA_DIR} --strip-components=1

  echo "--> Unpacking ./cypress/fixtures/${spec_file}_specterdir.tar.gz ... into ${SPECTER_DATA_FOLDER} ..."
  rm -rf $SPECTER_DATA_FOLDER
  mkdir $SPECTER_DATA_FOLDER 
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
    start_elementsd --cleanuphard
    start_specter
  else
    start_bitcoind --reset
    stop_elementsd --reset
    start_specter --reset
  fi
  open http://localhost:${PORT}
  sleep infinity
}

function sub_open {
  spec_file=$1
  if [ -n "${spec_file}" ]; then
    restore_snapshot ${spec_file}
    start_bitcoind
    start_elementsd
    start_specter
  else
    start_bitcoind --reset
    start_elementsd --reset
    start_specter --reset
  fi
  $(npm bin)/cypress open
}

function sub_run {
  spec_file=$1
  if [ -f ./cypress/integration/${spec_file} ]; then
    restore_snapshot ${spec_file}
    start_bitcoind 
    start_elementsd
    start_specter
    # Run $spec_file and all of the others coming later!
    #$(npm bin)/cypress run --spec $(./utils/calc_cypress_test_spec.py --run $spec_file)
    # Run $spec_file and only that spec-file!
    $(npm bin)/cypress run --spec ./cypress/integration/${spec_file}
  else 
    start_bitcoind --reset
    start_elementsd --reset
    start_specter --reset
    $(npm bin)/cypress run
  fi
}

function sub_basics {
  start_bitcoind --reset
  start_elementsd --reset
  start_specter --reset
  $(npm bin)/cypress run --spec $(./utils/cypress_basics.py) --config video=false
  $(npm bin)/cypress open
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
  start_elementsd --reset
  start_specter --reset
  $(npm bin)/cypress run --spec $(./utils/calc_cypress_test_spec.py $spec_file)
  echo "--> stopping specter"
  stop_specter
  echo "--> stopping bitcoind gracefully ... won't take long ..."
  stop_bitcoind
  echo "--> stopping elementsd gracefully ... won't take long ..."
  stop_elementsd
  echo "--> Creating snapshot $BTCD_REGTEST_DATA_DIR)"
  rm ./cypress/fixtures/${spec_file}_btcdir.tar.gz 2> /dev/null 1>&2 || :
  tar -czf ./cypress/fixtures/${spec_file}_btcdir.tar.gz -C /tmp $(basename $BTCD_REGTEST_DATA_DIR)
  echo "--> Creating snapshot $ELMD_REGTEST_DATA_DIR)"
  rm ./cypress/fixtures/${spec_file}_elmdir.tar.gz 2> /dev/null 1>&2 || :
  tar -czf ./cypress/fixtures/${spec_file}_elmdir.tar.gz -C /tmp $(basename $ELMD_REGTEST_DATA_DIR)
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

  # Don't start elementsd unless --with-elements is set
  # Usage: ./utils/test-cypress.sh --with-elements run
  USE_ELEMENTSD=false
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
    --elm-log-stdout)
      ELMLOGSTDOUT=true
      shift
      ;;
    --with-elements)
      USE_ELEMENTSD=true
      shift
      ;;
    *)
      shift
      START=$(date +%s)
      sub_${arg} $@
      END=$(date +%s)
      DIFF=$(echo "( $END - $START ) / 60" | bc)
      echo "    --> End $(date) took $DIFF minutes"
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
export ELECTRON_EXTRA_LAUNCH_ARGS=--lang=en
parse_and_execute $@

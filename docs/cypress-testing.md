# Cypress Tests

The UI is tested via [cypress](https://www.cypress.io/) which is built with node.js. The tests are specified in `cypress.json`. One of the challenges here is management of state (specter-folder and state of regtest/elements). cypress is [discouraging](https://docs.cypress.io/guides/references/best-practices.html#Web-Servers) to start/stop the web server or its prerequisites as part of executing the tests. Therefore we need to manage that ourselves.

The below stuff has been tested on Linux and MacOS. Linux is fully supported. The snapshot functionality works partially on MacOS. Windows is not supported at all.

So the tests in general are designed to run in a more or less strict sequence specified in cypress.json. So later tests might need the state created in former tests.

This is very different than on unit-tests and, with an increasing amount of tests, this might be cumbersome in order to only execute a specific test or develop on a specific one.

So there is the possibility to snapshot and restore the state of a specific test-run. Also, in parallel to running the pytests, it would be beneficial to not use the default-folders (`~/.specter` and ) for the state but completely separate that. This way, you can develop live on the application and running the tests in parallel without interference. Doing that is possible via test-cypress.sh:
```
$ ./utils/test-cypress.sh 
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
$
```
Apart from dealing with snapshots, it'll also take care to use different folders (`~/.specter-cypress` and `/tmp/specter_cypress_btc_regtest_plain_datadir` and a different port for specter (`25444` instead of `25441`). However, bitcoind-port is still the same. So currently you can't run bitcoind-regtest for development and do (reliable) tests with cypress. You will get failing tests in that case. Will get fixed in the future.

Let's look at some typical use-cases in order to understand how to use this script. In any case, you'll need nodejs installed, so do something like:
```
wget https://nodejs.org/dist/v15.3.0/node-v15.3.0-linux-x64.tar.xz
sudo tar -xJf node-v15.3.0-linux-x64.tar.xz -C /opt
sudo ln -s /opt/node-v15.3.0-linux-x64 /opt/node
export PATH=$PATH:/opt/node/bin # maybe make that permanent
npm ci
```

## Run tests
`./utils/test-cypress.sh run` will simply run all the tests. If there are any issues, you'll find screenshots of failed states and mp4-videos in `cypress/screenshots` and `cypress/videos`. These videos/screenshots are also available om cirrus.

## Interactively run tests
`./utils/test-cypress.sh open` will open the cypress application (after spinning up bitcoind-regtest and Specter). Here, you can choose the test-suite you want to execute. As the tests rely on the state of former-tests and we have a clean state, now, you have to run them in sequence no matter which test-file you're interested in. The tests are (and should be) written in a way that is resilient to this but that's especially difficult on the btc-regtest side of the story.

You can run the tests more than once but the regtest state will simply continue with its history. Especially if you want to focus on higher level tests (which are running later in the sequence), it's annoying to run all the tests before that.

This doesn't work yet reliable with MacOS.

## Create a snapshot
Let's say you want to focus on the currently last test-file `spec_wallet_utxo.js`. You can create a snapshot of the expected state at the start of the test via:
```
$ ./utils/test-cypress.sh snapshot # will output possible arguments
ERROR: Use one of these arguments:
spec_setup_wizard.js
spec_setup_tor.js
spec_empty_specter_home.js
spec_configures_nodes.js
spec_node_configured.js
spec_wallet_send.js
spec_wallet_utxo.js
spec_elm_single_segwit_wallet.js
spec_elm_multi_segwit_wallet.js
$ ./utils/test-cypress.sh snapshot spec_wallet_utxo.js
```
So this will now run all the tests in sequence up to (but not including) `spec_wallet_utxo.js` under the assumption that the tests will pass. After that it'll create a snapshot of that state and stored it in `./cypress/fixtures`.

## Run specific tests (with the help of snapshots)

Now you can run (or open) specifically this test-file via:
```
$ ./utils/test-cypress.sh run spec_wallet_utxo.js
```
This will restore the snapshot created above and run this test (and all subsequent ones). Opening the cypress app works the same although there you're responsible to be aware that the state is fitting to the spec-file you want to execute (just like in the case of empty state above)

## Develop based on the state of a specific snapshot

Maybe you'd like to test the application or develop on a specific snapshot. You can do that like this:
```
$ ./utils/test-cypress.sh dev spec_existing_history.js
```
This will restore the snapshot created above, run bitcoind-regtest/specter and will open the browser to operate on the application. It'll run in debug-state so that you can modify the source code right away.

This doesn't work yet reliable with MacOS.

## Develop on tests
The spec-files mainly select some element on a web page and then act on them. Mainly `.click()` and `.type("some Text")`. So it's quite helpful to have unique IDs for all the elements which we want to use in the tests. The cypress-app has a very convenient way of selecting. Make sure you don't miss that.

For specific things there are `cy.tasks` which can be implemented. Some of those are already existing, e.g.:
* purging the specter-folder is possible via `cy.task("clear:specter-home")`
* Mining some coins to each of the wallets defined in the specter-folder is possible via `cy.task("node:mine")`. Depending on the height of the blockchain, you might get very different results. The coins are immediately spendable.

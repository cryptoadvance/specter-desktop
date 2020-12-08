# Cypress Tests

The UI is tested via [cypress](https://www.cypress.io/) which is built with node.js. The tests are specified in `cypress.json`. One of the challenges here is management of state (specter-folder and state of regtest). cypress is [discouraging](https://docs.cypress.io/guides/references/best-practices.html#Web-Servers) to start/stop the webserver or its prerequisites as part of executing the tests. Therefore we need to manage that ourself.

 So the tests in general are designed to run in a strict sequence specified in cypress.json. So later tests might need the state created in former tests.

This is very different than on unit-tests and, with an increasing amount of tests, this might be cumbersome in order to only execute a specific test or develop on a specific one.
Therefore there is the possibility to snapshot and restore the state of a specific test-run. Also, in parallel to running the pytests, it would be beneficial to not use the default-folders (`~/.specter` and ) for the state but completely separate that. This way, you can develop live on the application and running the tests in parallel without interference. Doing that is possible via the test-cypress.sh:
```
$ ./utils/test-cypress.sh
Usage: ./utils/test-cypress.sh <subcommand> [options]
  Doing stuff with cypress-tests according to <subcommand>

Subcommands:
    open                  will open the cypress app.
    run                   will run the tests.
    snapshot <spec_file>  will create a snapshot of the spec-file. It will create a tarball
                          of the btc-dir and the specter-dir and store that file in the 
                          ./cypress/fixtures directory

open and run take a spec-file optionally. If you add a spec-file, then automatically the
corresponding snapshot is untarred before and, in the case of run, only the spec-file and
all subsequent spec_files are executed.

$
```
Apart from dealing with snapshots, it'll also take care to use different folders (`~/.specter-cypress` and `/tmp/specter_btcd_regtest_plain_datadir`)

Let's look at some typical use-cases in order to understand how to use this script. In any case, you'll need nodejs installed, so do something like:
```
wget https://nodejs.org/dist/v15.3.0/node-v15.3.0-linux-x64.tar.xz
sudo tar -xJf node-v15.3.0-linux-x64.tar.xz -C /opt
sudo ln -s /opt/node-v15.3.0-linux-x64 /opt/node
export PATH=$PATH:/opt/node/bin # maybe make that permanent
npm ci
```

## Run tests
`./utils/test-cypress.sh run` will simply run all the tests. If there are any issues, you'll find screenshots of failed states and mp4-videos in `cypress/screenshots` and `cypress/videos`. In the case of running in gitlab, thanks to the ["artifacts-section"](https://github.com/k9ert/specter-desktop/blob/cypress/.gitlab-ci.yml#L53-L58), you can watch them by browsing the artifacts on any gitlab-job-page (right-hand-side marked with "Job artifacts"). This will hopefully also be available on travis.

## Interactively run tests
`./utils/test-cypress.sh open` will open the cypress application (after spinning up bitcoind-regtest and specter). Here, you can choose the test-suite you want to execute. As the tests rely on the state of former-tests and we have a clean state, now, you have to run them in sequence no matter which test-file you're interested in. The tests are (and should be) written in a way that is resilient to this but that's especially difficult on the btc-regtest side of the story.

You can run the tests more than once but the regtest state will simply continue with its history. Especially if you want to focus on higher level tests (which are running later in the sequence), it's anoying to run all the tests before that.

## Create a snapshot
Let's say you want to focus on the currently last test-file `spec_existing_history`. You can create a snapshot of the expected state at the start of the test via:
```
$ ./utils/test-cypress.sh snapshot # will output possible arguments
we need one of these arguments:
spec_empty_specter_home.js
spec_node_configured.js
spec_existing_history.js
$ ./utils/test-cypress.sh snapshot spec_existing_history.js
```

Now you can run (or open) specifically this test-file via:
```
$ ./utils/test-cypress.sh run spec_existing_history.js
```
This will restore the snapshot created above and run this test (and all subsequent ones). Opening the cypress app works the same although there you're responsible to be aware that the state is fitting to the spec-file you want to execute (just like in the case of empty state above)

## Develop on tests
The spec-files mainly select some element on a webpage and then act on them. Mainly `.click()` and `.type("some Text")`. So it's quite helpfull to have unique IDs for all the elements which we want to use in the tests. The cypress-app has a very convenient way of selecting. Make sure you don't miss that.

For specific things there are `cy.tasks` which can be implemented. Two of the already existing tasks:
* purging the specter-folder is possible via `cy.task("clear:specter-home")`
* Mining some coins to each of the wallets defined in the specter-folder is possible via `cy.task("node:mine")`. Depending on the height of the blockchain, you might get very different results. The coins are immediately spendable.

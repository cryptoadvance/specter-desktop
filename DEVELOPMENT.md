<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**

- [Development](#development)
  - [How to run the Application](#how-to-run-the-application)
  - [Howto run the tests](#howto-run-the-tests)
  - [Code-Style](#code-style)
  - [Developing on tests](#developing-on-tests)
    - [bitcoin-specific stuff](#bitcoin-specific-stuff)
    - [Cypress UI-testing](#cypress-ui-testing)
  - [Flask specific stuff](#flask-specific-stuff)
  - [More on the bitcoind requirements](#more-on-the-bitcoind-requirements)
  - [IDE-specific Configuration (might be outdated)](#ide-specific-configuration-might-be-outdated)
    - [Visual Studio Code](#visual-studio-code)
      - [Debugging](#debugging)
      - [Unit-Tests](#unit-tests)
    - [PyCharm](#pycharm)
      - [Debugging](#debugging-1)
      - [Unit-Tests](#unit-tests-1)
  - [Guidelines and (for now) "best practices"](#guidelines-and-for-now-best-practices)
    - [General File Layout](#general-file-layout)
    - [Some words about dependencies](#some-words-about-dependencies)
    - [Some words specific to the frontend](#some-words-specific-to-the-frontend)
    - [Some words about style](#some-words-about-style)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Development

## How to run the Application

Install dependencies:

* Ubuntu/Debian: `sudo apt install libusb-1.0-0-dev libudev-dev`
* macOS: `brew install libusb`

Note that `hwi-1.2.0` needs Python 3.6-3.8. If you have Python 3.9 installed then be sure to also install an old Python version and pass it to `virtualenv`, .e.g `virtualenv --python3.8 .env`.

```sh
git clone https://github.com/cryptoadvance/specter-desktop.git
cd specter-desktop
virtualenv --python=python3 .env 
source .env/bin/activate
pip3 install -r requirements.txt --require-hashes
pip3 install -e .
```

Run the server:

```sh
cd specter-desktop
python3 -m cryptoadvance.specter server --config DevelopmentConfig
```

## Howto run the tests
Run the tests (still very limited):

```sh
pip3 install -r test_requirements.txt
pip3 install -e .

# needs a bitcoind on your path
pytest 

# needs a working docker-setup (but not bitcoind)
# prerequsisite: 
# docker pull registry.gitlab.com/cryptoadvance/specter-desktop/python-bitcoind:latest
pytest --docker 

# Run all the tests in a specific test-file
pytest tests/test_specter

# Run all tests in a specific file matching "Manager"
pytest tests/test_specter -k Manager 
```

Check the cypress-section on how to run cypress-frontend-tests.

## Code-Style

Before your create a PR, make sure to [blackify](https://github.com/psf/black) all your changes. In order to automate that,
there is a git pre-commit hook which you can simply install like this:
```
pre-commit install
```

## Developing on tests
We use pytest and for frontend-testing the amazing [cypress.io](https://www.cypress.io/).

### bitcoin-specific stuff

There are some things worth taking a note here, especially if you rely on a specific state on the blockchain for your tests. Bitcoind is started only once for all the tests. If you run 
it each time it's starting with the genesis-block. This has some implications:
* The [halving-interval for regtest](https://github.com/bitcoin/bitcoin/blob/99813a9745fe10a58bedd7a4cb721faf14f907a4/src/chainparams.cpp#L258) is only 150-blocks
* At the same time, still 100 blocks need to be minded in order to make the coins spendable.
* This combination results in that you can't rely on how many coins get mined if you want some testcoin on your address
* This also means that it makes a huge difference whether you run a test standalone or together with all other tests
* Depending on whether you do one or the other, you cannot rely on transactionIDs. So if you run a test standalone twice, you can assert txids but you can't any longer when you run all the tests

### Cypress UI-testing
Cypress is just awesome. It's quite easy to create Frontend-tests and it's even recording all tests and you can immediately see how it went. So each test-run, the tests are kept for one day (see the ["artifacts-section"](https://github.com/k9ert/specter-desktop/blob/cypress/.gitlab-ci.yml#L53-L58)) and you can watch them by browsing the artifacts on any gitlab-job-page (right-hand-side marked with "Job artifacts").

Executing the tests is done via `./utils/test-cypress.sh`:
```
# make sure you have npm on the path

# run the tests
./utils/test-cypress.sh run
# open the cypress application (to develop/debug/run tests interactively)
./utils/test-cypress.sh open
```
The test_specifications which get executed are specified in cypress.json which looks something like this:

More details on cypress-testing can be found in [cypress-testing.md](docs/cypress-testing.md).
Make sure to read it. The tooling we created around cypress quite helpful in daily development.
In short, you can do this and the last command will give you a reliable development-environment which is the very same
whenever you start it anew:
```
./utils/test-cypress.sh snapshot spec_existing_history.js
./utils/test-cypress.sh dev spec_existing_history.js
# CTRL-C
./utils/test-cypress.sh dev spec_existing_history.js
# CTRL-C
[...]
```

## Flask specific stuff

Other than Django, Flask is not opionoated at all. You can do all sorts of things and it's quite difficult to judge whether you're doing it right.

One strange thing which we're doing to get the tests working is forcing the reload of the controller-code (if necessary) [here](https://github.com/cryptoadvance/specter-desktop/blob/master/src/cryptoadvance/specter/server.py#L88-L93).

The if-clause might be quite brittle which would result in very strange 404 in test_controller.
Check the [archblog](./docs/archblog.md) for a better explanation.
If Someone could figure out a better way to do that avoiding this strange this ... very welcome.

## More on the bitcoind requirements
Developing against a bitcoind-API makes most sense with the [Regtest Mode](https://bitcoin.org/en/developer-examples#regtest-mode). Depending on preferences and usecases, there are three major ways on how this dependency can be fullfilled:
* Easiest way via Docker
* The unittests on Travis-CI are using a script which is installing and compiling bitcoind
* bitcoind is manually started (out of scope for this document)

In order to make the "docker-way" even easier, there is a python-script which detects a running-docker-bitcoind and/or is booting one up. Use it like this:

```
python3 -m cryptoadvance.specter bitcoind
```

This will also:
* automatically mine some coins for the addresses found in the wallets at ~/.specter/wallets/regtest/*.json 
* automatically mine a block every 15 seconds (but not to the wallet-addresses anymore)

However, this is NOT a prerequisite for running the tests (--docker or not).

After that, you can configure the bitcoin-core-connection in specter-desktop like this:
* Username: bitcoin
* Password: secret
* Host: localhost
* Port: 18443

## IDE-specific Configuration (might be outdated)

### Visual Studio Code

#### Debugging
You can easily create a .vscode/launch.json file via the debug-window. However this setup won't work properly because the python-environment won't be on the PATH but the hwi-executable need to be available in the PATH. So adding the PATH with something like the below is working with VS-COde 1.41.1 and the python-plugin 2019.11.50794.


```json5
{
    // Use IntelliSense to learn about possible attributes.
    // Hover to view descriptions of existing attributes.
    // For more information, visit: https://go.microsoft.com/fwlink/?linkid=830387
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Flask",
            "type": "python",
            "request": "launch",
            "module": "flask",
            "env": {
                "FLASK_APP": "cryptoadvance.specter.server:create_and_init()",
                "FLASK_ENV": "development",
                "FLASK_DEBUG": "1",
                "PATH": "./.env/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
            },
            "args": [
                "run",
                "--no-debugger",
                "--no-reload"
            ],
            "jinja": true
        }
    ]
}
```

More information on debugging can be found at the [python-tutorial](https://code.visualstudio.com/docs/python/python-tutorial#_configure-and-run-the-debugger).

#### Unit-Tests
In VS-Code there is a very convenient way of running/debugging the tests:
<img src=https://code.visualstudio.com/assets/docs/python/testing/editor-adornments-unittest.png>  
In order to enable that, you need to activate pytest support by placing a settings.json file like this in .vscode/settings.json:

```json5
{
    "python.pythonPath": ".env/bin/python3.7",
    "python.testing.unittestEnabled": false,
    "python.testing.nosetestsEnabled": false,
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["--docker"]
}
```
**WARNING**: Make sure to never stop a unittest in between. Simply continue with the test and let it run through. Otherwise the docker-container used for the test won't get cleaned up and your subsequent test-runs will fail with strange issues. If you did that, simply kill the container (```docker ps; docker kill ...```)

More information on python-unit-tests on VS-Code can be found at the [VS-python-documentation](https://code.visualstudio.com/docs/python/testing).

### PyCharm
| Edition       | Version           |
| ------------- |:-------------:|
| [PyCharm Community](https://www.jetbrains.com/pycharm/download)     | 2020.3.2 |
#### Debugging
Once the project is setup and all dependencies are installed:
* Create a new xml file under `<PROJECT_ROOT>/.idea/runConfigurations/specter-server.xml`
* Open the file, paste the xml from below and save
* Restart the IDE

You should now be able to run and debug the application from the PyCharm run panel!
```xml
<component name="ProjectRunConfigurationManager">
  <configuration default="false" name="specter-server" type="PythonConfigurationType" factoryName="Python">
    <module name="specter-desktop" />
    <option name="INTERPRETER_OPTIONS" value="" />
    <option name="PARENT_ENVS" value="true" />
    <envs>
      <env name="PYTHONUNBUFFERED" value="1" />
      <env name="FLASK_APP" value="cryptoadvance.specter.server:create_and_init()" />
      <env name="FLASK_ENV" value="development" />
      <env name="FLASK_DEBUG" value="1" />
      <env name="PATH" value="./.env/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" />
    </envs>
    <option name="SDK_HOME" value="" />
    <option name="WORKING_DIRECTORY" value="$PROJECT_DIR$" />
    <option name="IS_MODULE_SDK" value="true" />
    <option name="ADD_CONTENT_ROOTS" value="true" />
    <option name="ADD_SOURCE_ROOTS" value="true" />
    <option name="SCRIPT_NAME" value="flask" />
    <option name="PARAMETERS" value="run --no-debugger --no-reload" />
    <option name="SHOW_COMMAND_LINE" value="false" />
    <option name="EMULATE_TERMINAL" value="false" />
    <option name="MODULE_MODE" value="true" />
    <option name="REDIRECT_INPUT" value="false" />
    <option name="INPUT_FILE" value="" />
    <method v="2" />
  </configuration>
</component>
```

#### Unit-Tests
PyCharm already comes with integrated support for pyTest. 

To run/debug all tests:
* Right click on the `<PROJECT_ROOT>/test` folder and execute `Run pytest in tests`
* Edit the automatically generated run configuration and optionally add the `--docker` argument, change the working directory to your `<PROJECT_ROOT>` directory
* Apply, Save & Run again

To run/debug an individual test, open the script and run/debug by clicking the play icon on the left side of the method declaration.
<img src=https://resources.jetbrains.com/help/img/idea/2020.3/py_pytest_run_debug_configuration.png> 

## Guidelines and (for now) "best practices"

### General File Layout
Python/flask is not very opinionated and everything is possible. After reading (this)[https://blog.ionelmc.ro/2014/05/25/python-packaging/#the-structure] and (this)[https://blog.ionelmc.ro/2014/05/25/python-packaging/#the-structure] we decided for the "src-approach", at least the most obvious parts of it.

setup.py is not (yet) as complex as listed there and setup.cfg is not even (yet?!) existing.
If you see this to need some improvements, please make it in small steps and explain what the benefits of all of that.

### Some words about dependencies
As a quite young project, we don't have many dependencies yet and as a quite secure-aware use-case, we don't even want to have too many dependencies. That's sometimes the reason that we decide to roll our own rather then taking in new dependencies. This is especially true for javascript. We prefer plain javascript over any kind of frameworks.

If you update `requirements.in` you will need to run the following to update `requirements.txt`:
```sh
$ pip-compile --generate-hashes requirements.in
```

This is good for both security and reproducibility.

### Some words specific to the frontend
We're aware that currently the app is not very compatible on different browsers and there is no clear strategy yet on how (and whether at all) to fix that.

### Some words about style
* The icons are coming from https://material.io/resources/icons/?style=baseline
* Colorizing the icons make them much more expressive. Current favorite colors are:
  * nice orange #F5A623
  * nice blue #4A90E2
* A designer would probably rant about all these bad choices. Professional help, especially in the frontend, is very much appreciated.


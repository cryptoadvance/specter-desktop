# Run the tests
Run the tests (still very limited):

```
pip3 install -e .
pytest # needs a bitcoind on your path
pytest --docker # needs a working docker-setup (but not bitcoind)
pytest tests/test_specter -k Manager # Run all tests in a specific file matching "Manager"
```

# More on the bitcoind requirements
Developing against a bitcoind-API makes most sense with the [Regtest Mode](https://bitcoin.org/en/developer-examples#regtest-mode). Depending on preferences and usecases, there are three major ways on how this dependency can be fullfilled:
* Easiest way via Docker
* The unittests on Travis-CI are using a script which is installing and compiling bitcoind
* bitcoind is manually started (out of scope for this document)

In order to make the "docker-way" even easier, there is a python-script which detects a running-docker-bitcoind and/or is booting one up. Use it like this:

```
python3 src/specter/cli.py bitcoind
```

This will also:
* automatically mine some coins for the addresses found in the wallets at ~/.specter/wallets/regtest/*.json 
* automatically mine a block every 15 seconds (but not to the wallet-addresses anymore)

# IDE-specific Configuration

## Unit-Tests in VS-Code
In VS-Code there is a very convenient way of running/debugging the tests:
<img src=https://code.visualstudio.com/assets/docs/python/testing/editor-adornments-unittest.png>
In order to enable that, you need to activate pytest support by placing a settings.json file like this in .vscode/settings.json:

```
{
    "python.pythonPath": ".env/bin/python3.7",
    "python.testing.unittestEnabled": false,
    "python.testing.nosetestsEnabled": false,
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["--docker"]
}
```
More information on python-unit-tests on VS-Code can be found at the [VS-python-documentation](https://code.visualstudio.com/docs/python/testing).

## Debugging in VS-Code
You can easily create a .vscode/launch.json file via the debug-window. However this setup won't work properly because the python-environment won't be on the PATH but the hwi-executable need to be available in the PATH. So adding the PATH with something like the below is working with VS-COde 1.41.1 and the python-plugin 2019.11.50794.


```
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
                "FLASK_APP": "server.py",
                "FLASK_ENV": "development",
                "FLASK_DEBUG": "0",
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

# General File Layout
Python/flask is not very opinionated and everything is possible. After reading (this)[https://blog.ionelmc.ro/2014/05/25/python-packaging/#the-structure] and (this)[https://blog.ionelmc.ro/2014/05/25/python-packaging/#the-structure] we decided for the "src-approach", at least the most obvious parts of it.

setup.py is not (yet) as complex as listed there and setup.cfg is not even (yet?!) existing.
If you see this to need some improvements, please make it in small steps and explain what the benefits of all of that.

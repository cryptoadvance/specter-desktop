import logging
import multiprocessing
import os
import signal
import sys
import time
from os import path, name
from socket import gethostname
from urllib.parse import urlparse

import click

try:
    from cryptoadvance.specter.gunicorn import SpecterGunicornApp
except ModuleNotFoundError as e:
    # gunicorn is not supported on windows
    if os.name == "nt":
        pass
    else:
        raise e
from cryptoadvance.specter.server import create_and_init, create_app, init_app
from OpenSSL import SSL, crypto
from stem.control import Controller

from ..server import create_app, init_app
from ..specter_error import SpecterError
from ..util.tor import start_hidden_service, stop_hidden_services

logger = logging.getLogger(__name__)


@click.group()
def cli():
    pass


@cli.command()
def gunicorn():
    # fmt: off
    """uses gunicorn instead of the build in development-server.
    
    This works mostly like in https://docs.gunicorn.org/en/latest/run.html just that you use
    this command rather than gunicorn. As recommended there, everything Application
    specific needs to be configured via envirnoment Vars. See cryptoadvance.specter.config for
    how to configure most specter-sepcific things.

    Other than running gunicorn's executable directly, you can't specify command-line
    paramaters. Here are some configurations you can do:

    \b
    GUNICORN_CMD_ARGS="--bind=127.0.0.1 --workers=3" \ 
      python3 -m cryptoadvance.specter gunicorn
    
    You can use a config file named gunicorn.conf.py in the same directory:

    \b
    workers=10

    Commandline paramater trums env-var params.
    You can specify hook functions in the gunicorn.conf.py, see this for a list of them:
    https://docs.gunicorn.org/en/latest/settings.html#server-hooks

    e.g.:

    \b
    def on_starting(server):
        print("Called just before the master process is initialized.")
    
    More information directly in the gunicorn-Documentation

    """
    if os.name == "nt":
        print("Sorry, gunicorn is not available on windows")
        exit(1)
    specter_gunicorn = SpecterGunicornApp(config=None)
    specter_gunicorn.run()

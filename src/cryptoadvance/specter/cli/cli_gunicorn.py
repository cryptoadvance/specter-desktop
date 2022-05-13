import logging
import multiprocessing
import os
import signal
import sys
import time
from os import path
from socket import gethostname
from urllib.parse import urlparse

import click
from cryptoadvance.specter.gunicorn import SpecterGunicornApp
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
# options below can help to run it on a remote server,
# but better use nginx
@click.option(
    "--port", default=25441, help="TCP port to bind specter to"
)  # default - 25441 set to 80 for http, 443 for https
# set to 0.0.0.0 to make it available outside
@click.option(
    "--host",
    default="127.0.0.1",
    help="if you specify --host 0.0.0.0 then specter will be available in your local LAN.",
)
@click.option("--debug/--no-debug", default=None)
@click.option(
    "--config",
    default=None,
    help="A class from the config.py which sets reasonable default values.",
)
def gunicorn(
    port,
    host,
    debug,
    config,
):
    """uses gunicorn instead of the build in development-server.
    Less option but maybe also better scalable. In principal, it's very similiar to the server-command
    but you can't use it for the hwiBridge, using tor or creating certs out of the box.
    It's considered to be beta.
    """
    # logging
    if debug:
        ca_logger = logging.getLogger("cryptoadvance")
        ca_logger.setLevel(logging.DEBUG)
        logger.debug("We're now on level DEBUG on logger cryptoadvance")

    options = {
        "bind": "%s:%s" % (host, port),
        "workers": 1,
    }
    specter_gunicorn = SpecterGunicornApp(config=config, options=options)
    specter_gunicorn.run()

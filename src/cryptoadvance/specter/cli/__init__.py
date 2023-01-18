import logging
import os
from http.client import HTTPConnection

import click

from .cli_noded import bitcoind, elementsd
from .cli_ext import ext
from .cli_server import server
from .cli_gunicorn import gunicorn
from .utils import setup_logging

logger = logging.getLogger(__name__)


@click.group()
@click.option("--debug", is_flag=True, help="Show debug information on errors.")
@click.option(
    "--tracerpc/--no-tracerpc",
    default=False,
    help="Will trace all calls to BitcoinCore or ElementsCore if in --debug",
)
@click.option(
    "--tracerequests/--no-tracerequests",
    default=False,
    help="Will trace all calls done via the requests module. Might be quite verbose!",
)
@click.pass_context
def entry_point(config_home, debug=False, tracerpc=False, tracerequests=False):
    setup_logging(debug, tracerpc, tracerequests)


entry_point.add_command(server)
entry_point.add_command(gunicorn)
entry_point.add_command(ext)
entry_point.add_command(bitcoind)
entry_point.add_command(elementsd)

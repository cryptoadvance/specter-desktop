import logging
import os
from http.client import HTTPConnection

import click

from .cli_noded import bitcoind, elementsd
from .cli_ext import ext
from .cli_server import server
from .cli_gunicorn import gunicorn

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
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    if tracerpc or tracerequests:
        if tracerpc:
            debug = True  # otherwise this won't work
            logging.getLogger("cryptoadvance.specter.rpc").setLevel(logging.DEBUG)
        if tracerequests:
            # from here: https://stackoverflow.com/questions/16337511/log-all-requests-from-the-python-requests-module
            HTTPConnection.debuglevel = 1
            requests_log = logging.getLogger("requests.packages.urllib3")
            requests_log.setLevel(logging.DEBUG)
            requests_log.propagate = True
    else:
        logging.getLogger("cryptoadvance.specter.rpc").setLevel(logging.INFO)

    if debug:
        # No need for timestamps while developing
        formatter = logging.Formatter("[%(levelname)7s] in %(module)15s: %(message)s")
        logging.getLogger("cryptoadvance").setLevel(logging.DEBUG)
        # but not that chatty connectionpool
        logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
    else:
        formatter = logging.Formatter(
            # Too early to format that via the flask-config, so let's copy it from there:
            os.getenv(
                "SPECTER_LOGFORMAT",
                "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
            )
        )
        logging.getLogger("cryptoadvance").setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logging.getLogger().handlers = []
    logging.getLogger().addHandler(ch)


entry_point.add_command(server)
entry_point.add_command(gunicorn)
entry_point.add_command(ext)
entry_point.add_command(bitcoind)
entry_point.add_command(elementsd)

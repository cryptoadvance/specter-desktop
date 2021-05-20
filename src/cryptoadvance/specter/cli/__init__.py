import logging
import click
from .cli_server import server
from .cli_noded import bitcoind, elementsd

logger = logging.getLogger(__name__)


@click.group()
@click.option("--debug", is_flag=True, help="Show debug information on errors.")
@click.pass_context
def entry_point(config_home, debug=False):
    # ctx.obj = Repo(config_home, debug)
    if debug:
        logging.basicConfig(level=logging.DEBUG)
        logging.getLogger("cryptoadvance").setLevel(logging.DEBUG)
    logger


entry_point.add_command(server)
entry_point.add_command(bitcoind)
entry_point.add_command(elementsd)

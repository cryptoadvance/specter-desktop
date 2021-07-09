import logging
import click
from .cli_server import server
from .cli_noded import bitcoind, elementsd

logger = logging.getLogger(__name__)


@click.group()
@click.option("--debug", is_flag=True, help="Show debug information on errors.")
@click.option(
    "--tracerpc/--no-tracerpc",
    default=False,
    help="Will trace all calls to BitcoinCore or ElementsCore if in --debug",
)
@click.pass_context
def entry_point(config_home, debug=False, tracerpc=False):
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    if debug:
        # No need for timestamps while developing
        formatter = logging.Formatter("[%(levelname)7s] in %(module)15s: %(message)s")
        logging.getLogger("cryptoadvance").setLevel(logging.DEBUG)
    else:
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
        )
        logging.getLogger("cryptoadvance").setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logging.getLogger().addHandler(ch)

    if tracerpc:
        if not debug:
            raise Exception("--tracerpc Doesn't make sense without --debug")
        logging.getLogger("cryptoadvance.specter.rpc").setLevel(logging.DEBUG)
    else:
        logging.getLogger("cryptoadvance.specter.rpc").setLevel(logging.INFO)


entry_point.add_command(server)
entry_point.add_command(bitcoind)
entry_point.add_command(elementsd)

from cryptoadvance.specter.cli import entry_point
from cryptoadvance.specter.cli.cli_server import server
import logging
import click

logger = logging.getLogger(__name__)


@click.group()
def cli():
    pass


@cli.command()
@click.pass_context
@click.option(
    "--host",
    default="127.0.0.1",
    help="if you specify --host 0.0.0.0 then Notifications will be available in your local LAN.",
)
@click.option(
    "--ssl/--no-ssl",
    is_flag=True,
    default=False,
    help="By default SSL encryption will not be used. Use -ssl to create a self-signed certificate for SSL encryption.",
)
@click.option("--debug/--no-debug", default=None)
@click.option("--filelog/--no-filelog", default=True)
@click.option(
    "--config",
    default=None,
    help="A class which sets reasonable default values.",
)
def start(ctx, host, ssl, debug, filelog, config):
    if config == None:
        config = "cryptoadvance.specterext.notifications.config.AppProductionConfig"
    ctx.invoke(
        server,
        host=host,
        ssl=ssl,
        debug=debug,
        filelog=filelog,
        port=8080,
        config=config,
    )


entry_point.add_command(start)

if __name__ == "__main__":
    entry_point()

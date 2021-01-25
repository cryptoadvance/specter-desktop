import logging
import os
import shutil
import signal
import sys
import atexit
import time
import json
from pathlib import Path

import click
import psutil
from flask import Config

from ..config import DEFAULT_CONFIG

logger = logging.getLogger(__name__)


class Echo:
    def __init__(self, quiet):
        self.quiet = quiet

    def echo(self, mystring, prefix=True, **kwargs):
        if self.quiet:
            pass
        else:
            if prefix:
                click.echo(f"    --> ", nl=False)
            click.echo(f"{mystring}", **kwargs)


@click.command()
@click.option("--debug/--no-debug", default=False, help="Turns on debug-logging")
@click.option("--quiet/--no-quiet", default=False, help="as less output as possible")
@click.option(
    "--nodocker", default=False, is_flag=True, help="use without docker (non-default)"
)
@click.option(
    "--docker-tag", "docker_tag", default="latest", help="Use a specific docker-tag"
)
@click.option(
    "--data-dir",
    help="specify a (maybe not yet existing) datadir. Works only in --nodocker (Default:/tmp/bitcoind_plain_datadir) ",
)
@click.option(
    "--mining/--no-mining",
    default=True,
    help="Turns on mining (default). In tests it's useful to turn it off.",
)
@click.option(
    "--mining-period",
    default="15",
    help="Every mining-period (in seconds), a block gets mined (default 15sec)",
)
@click.option(
    "--reset",
    is_flag=True,
    default=False,
    help="Will kill the bitcoind. Datadir will get lost.",
)
@click.option(
    "--create-conn-json",
    is_flag=True,
    default=False,
    help="Will create a small json-file btcd-conn.json with connection details.",
)
@click.option(
    "--cleanuphard/--no-cleanuphard",
    default=False,
    help="Will send a SIGKILL instead of SIGTERM (default) when CTRL-C. Mostly to speedup tests.",
)
@click.option(
    "--config",
    default=None,
    help="A class from the config.py which sets reasonable Defaults",
)
def bitcoind(
    debug,
    quiet,
    nodocker,
    docker_tag,
    data_dir,
    mining,
    mining_period,
    reset,
    create_conn_json,
    cleanuphard,
    config,
):
    """This will start a bitcoind regtest and mines a block every mining-period.
    If a bitcoind is already running on port 18443, it won't start another one. If you CTRL-C this, the bitcoind will
    still continue to run. You have to shut it down.
    """
    # In order to avoid these dependencies for production use, we're importing them here:
    import docker

    from ..bitcoind import BitcoindDockerController, BitcoindPlainController

    if config is None:
        config = DEFAULT_CONFIG
    else:
        if not "." in config:
            config = "cryptoadvance.specter.config." + config
    config_obj = Config(".")
    config_obj.from_object(config)

    echo = Echo(quiet).echo

    if debug:
        echo(
            "Sorry, --debug used this way is deprecated. This feature will get removed. Please do it like this:"
        )
        echo("$ python3 -m cryptoadvance-specter --debug bitcoind")
        exit(1)

    if data_dir:
        config_obj["BTCD_REGTEST_DATA_DIR"] = data_dir

    if reset:
        if not nodocker:
            echo("ERROR: --reset only works in conjunction with --nodocker currently")
            return
        did_something = False

        for proc in psutil.process_iter():
            try:
                # Get process name & pid from process object.
                processName = proc.name()
                pid = proc.pid
                if processName.startswith("bitcoind"):
                    echo(f"Killing bitcoind-process with id {pid} ...")
                    did_something = True
                    os.kill(pid, signal.SIGTERM)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                echo(f"Pid {pid} not owned by us. Might be a docker-process? {proc}")
        if Path(config_obj["BTCD_REGTEST_DATA_DIR"]).exists():
            echo(f"Purging Datadirectory {config_obj['BTCD_REGTEST_DATA_DIR']} ...")
            did_something = True
            shutil.rmtree(config_obj["BTCD_REGTEST_DATA_DIR"])
        if not did_something:
            echo("Nothing to do!")
        return
    mining_every_x_seconds = float(mining_period)
    if nodocker:
        echo("starting plain bitcoind")
        if os.path.isfile("tests/bitcoin/src/bitcoind"):
            my_bitcoind = BitcoindPlainController(
                bitcoind_path="tests/bitcoin/src/bitcoind"
            )  # always prefer the self-compiled bitcoind if existing
        else:
            my_bitcoind = (
                BitcoindPlainController()
            )  # Alternatively take the one on the path for now
        # Make sure datadir does exist if specified:
        Path(config_obj["BTCD_REGTEST_DATA_DIR"]).mkdir(parents=True, exist_ok=True)
    else:
        echo("starting container")
        my_bitcoind = BitcoindDockerController(docker_tag=docker_tag)
    try:
        my_bitcoind.start_bitcoind(
            cleanup_at_exit=True,
            cleanup_hard=cleanuphard,
            datadir=config_obj["BTCD_REGTEST_DATA_DIR"],
        )
    except docker.errors.ImageNotFound:
        echo(f"Image with tag {docker_tag} does not exist!")
        echo(
            f"Try to download first with docker pull registry.gitlab.com/cryptoadvance/specter-desktop/python-bitcoind:{docker_tag}"
        )
        sys.exit(1)
    if not nodocker:
        tags_of_image = [
            image.split(":")[-1] for image in my_bitcoind.btcd_container.image.tags
        ]
        if docker_tag not in tags_of_image:
            echo(
                "The running docker container is not \
                                the tag you requested!"
            )
            echo(
                "please stop first with docker stop {}".format(
                    my_bitcoind.btcd_container.id
                )
            )
            sys.exit(1)
        echo("containerImage: %s" % my_bitcoind.btcd_container.image.tags)
    echo("           url: %s" % my_bitcoind.rpcconn.render_url())
    echo("user, password: bitcoin, secret")
    echo("    host, port: localhost, 18443")
    echo(
        "   bitcoin-cli: bitcoin-cli -regtest -rpcuser=bitcoin -rpcpassword=secret getblockchaininfo "
    )

    if create_conn_json:
        conn = my_bitcoind.rpcconn.as_data()
        conn["pid"] = os.getpid()  # usefull to send signals
        conn["specter_data_folder"] = config_obj[
            "SPECTER_DATA_FOLDER"
        ]  # e.g. cypress might want to know where we're mining to
        with open("btcd-conn.json", "w") as file:
            file.write(json.dumps(conn))

        def cleanup():
            os.remove("btcd-conn.json")

        atexit.register(cleanup)

    signal.signal(
        signal.SIGUSR1,
        lambda x, y: mine_2_specter_wallets(
            my_bitcoind, config_obj["SPECTER_DATA_FOLDER"], echo
        ),
    )

    if mining:
        miner_loop(
            my_bitcoind, config_obj["SPECTER_DATA_FOLDER"], mining_every_x_seconds, echo
        )


def miner_loop(my_bitcoind, data_folder, mining_every_x_seconds, echo):
    " An endless loop mining bitcoin "

    echo(
        "Now, mining a block every %f seconds, avoid it via --no-mining"
        % mining_every_x_seconds
    )
    mine_2_specter_wallets(my_bitcoind, data_folder, echo)

    # make them spendable
    my_bitcoind.mine(block_count=100)
    echo(
        f"height: {my_bitcoind.rpcconn.get_rpc().getblockchaininfo()['blocks']} | ",
        nl=False,
    )
    i = 0
    while True:
        try:
            my_bitcoind.mine()
            current_height = my_bitcoind.rpcconn.get_rpc().getblockchaininfo()["blocks"]
        except Exception as e:
            logger.debug(
                "Caught {e}, Couldn't mine, assume SIGTERM occured => exiting!"
            )
            echo(f"THE_END(@height:{current_height})")
            break
        echo("%i" % (i % 10), prefix=False, nl=False)
        if i % 10 == 9:
            echo(" ", prefix=False, nl=False)
        i += 1
        if i >= 50:
            i = 0
            echo("", prefix=False)
            echo(
                f"height: {current_height} | ",
                nl=False,
            )
        time.sleep(mining_every_x_seconds)


def mine_2_specter_wallets(my_bitcoind, data_folder, echo):
    """Get each specter-wallet some coins"""

    from ..bitcoind import fetch_wallet_addresses_for_mining

    try:

        for address in fetch_wallet_addresses_for_mining(data_folder):
            echo("")
            echo(f"Mining to address {address}")
            my_bitcoind.mine(address=address)
        my_bitcoind.mine(block_count=100)
    except FileNotFoundError:
        # might happen if there no ~/.specter folder yet
        pass

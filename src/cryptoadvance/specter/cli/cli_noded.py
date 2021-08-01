import atexit
import json
import logging
import os
import shutil
import signal
import sys
import time
from pathlib import Path

import click
import psutil
from flask import Config

from ..config import DEFAULT_CONFIG
from ..process_controller.node_controller import find_node_executable
from ..process_controller.elementsd_controller import ElementsPlainController
from .utils import (
    Echo,
    kill_node_process,
    purge_node_data_dir,
    compute_data_dir_and_set_config_obj,
)

logger = logging.getLogger(__name__)

# ------------------------bitcoind -----------------------------------------------------


@click.command()
@click.option("--quiet/--no-quiet", default=False, help="Output as little as possible.")
@click.option(
    "--nodocker",
    default=False,
    is_flag=True,
    help="Use without docker. (By default docker is used.)",
)
@click.option(
    "--docker-tag", "docker_tag", default="latest", help="Use a specific docker-tag"
)
@click.option(
    "--data-dir",
    help="Specify a (maybe not yet existing) datadir. Works only with --nodocker. (Default is /tmp/bitcoind_plain_datadir)",
)
@click.option(
    "--mining/--no-mining",
    default=True,
    help="Turns on mining (On by default). For testing it is useful to turn it off.",
)
@click.option(
    "--mining-period",
    default="15",
    help="Specify mining period (in seconds). Every N seconds a block gets mined. (Default is 15sec)",
)
@click.option(
    "--reset",
    is_flag=True,
    default=False,
    help="Kill the bitcoind daemon. Datadir will get lost.",
)
@click.option(
    "--create-conn-json",
    is_flag=True,
    default=False,
    help="Create a small json-file named btcd-conn.json with connection details.",
)
@click.option(
    "--cleanuphard/--no-cleanuphard",
    default=False,
    help="Send signal SIGKILL instead of SIGTERM (default) when CTRL-C is pressed. Mostly to speed up tests.",
)
@click.option(
    "--config",
    default=None,
    help="A class from the config.py which sets reasonable default values.",
)
def bitcoind(
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
    noded(
        "bitcoin",
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
    )


# ------------------------elementsd -----------------------------------------------------


@click.command()
@click.option("--quiet/--no-quiet", default=False, help="Output as little as possible.")
@click.option(
    "--data-dir",
    help="Specify a (maybe not yet existing) datadir. Works only with --nodocker. (Default is /tmp/bitcoind_plain_datadir)",
)
@click.option(
    "--mining/--no-mining",
    default=True,
    help="Turns on mining (On by default). For testing it is useful to turn it off.",
)
@click.option(
    "--mining-period",
    default="15",
    help="Specify mining period (in seconds). Every N seconds a block gets mined. (Default is 15sec)",
)
@click.option(
    "--reset",
    is_flag=True,
    default=False,
    help="Kill the bitcoind daemon. Datadir will get lost.",
)
@click.option(
    "--create-conn-json",
    is_flag=True,
    default=False,
    help="Create a small json-file named btcd-conn.json with connection details.",
)
@click.option(
    "--cleanuphard/--no-cleanuphard",
    default=False,
    help="Send signal SIGKILL instead of SIGTERM (default) when CTRL-C is pressed. Mostly to speed up tests.",
)
@click.option(
    "--config",
    default=None,
    help="A class from the config.py which sets reasonable default values.",
)
def elementsd(
    quiet,
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
    noded(
        "elements",
        quiet,
        True,  # nodocker
        None,  # docker_tag
        data_dir,
        mining,
        mining_period,
        reset,
        create_conn_json,
        cleanuphard,
        config,
    )


def noded(
    node_impl,
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
    """This will start a noded (depending on node_impl) regtest and mines a block every mining-period.
    If a node_impl is already running on port ?, it won't start another one. If you CTRL-C this, the node_impl will
    still continue to run. You have to shut it down yourself.
    """
    logger.debug("If you can read, this, logging is on debug")
    # In order to avoid these dependencies for production use, we're importing them here:
    import docker

    from ..process_controller.bitcoind_controller import BitcoindPlainController

    if config is None:
        config = DEFAULT_CONFIG
    else:
        if not "." in config:
            config = "cryptoadvance.specter.config." + config
    config_obj = Config(".")
    config_obj.from_object(config)

    echo = Echo(quiet).echo

    data_dir = compute_data_dir_and_set_config_obj(node_impl, data_dir, config_obj)

    if reset:
        if not nodocker:
            echo("ERROR: --reset only works in conjunction with --nodocker currently")
            return
        did_something = kill_node_process(node_impl, echo)
        did_something = (
            purge_node_data_dir(node_impl, config_obj, echo) or did_something
        )
        if not did_something:
            echo("Nothing to do!")
        return
    mining_every_x_seconds = float(mining_period)
    if nodocker:
        echo(f"Creating plain {node_impl}d")
        if node_impl == "bitcoin":
            my_node = BitcoindPlainController(
                bitcoind_path=find_node_executable("bitcoin")
            )
        elif node_impl == "elements":
            my_node = ElementsPlainController(
                elementsd_path=find_node_executable("elements")
            )
        Path(data_dir).mkdir(parents=True, exist_ok=True)
    else:
        echo("Creating container")
        from ..process_controller.bitcoind_docker_controller import (
            BitcoindDockerController,
        )

        if node_impl == "bitcoin":
            my_node = BitcoindDockerController(docker_tag=docker_tag)
        else:
            raise Exception("There is no Elementsd-Bitcoin-Controller yet!")
    try:
        echo(f"Starting {node_impl}d")
        if node_impl == "bitcoin":
            my_node.start_bitcoind(
                cleanup_at_exit=True,
                cleanup_hard=cleanuphard,
                datadir=data_dir,
            )
        elif node_impl == "elements":
            my_node.start_elementsd(
                cleanup_at_exit=True,
                cleanup_hard=cleanuphard,
                datadir=data_dir,
            )
    except docker.errors.ImageNotFound:
        echo(f"Image with tag {docker_tag} does not exist!")
        echo(
            f"Try to download first with docker pull registry.gitlab.com/cryptoadvance/specter-desktop/python-bitcoind:{docker_tag}"
        )
        sys.exit(1)
    except Exception as e:
        if str(e).startswith("There is already a node running!"):
            echo(f"{e} please reset via:")
            echo(f"python3 -m cryptoadvance.specter {node_impl}d --reset")
    if not nodocker:
        tags_of_image = [
            image.split(":")[-1] for image in my_node.btcd_container.image.tags
        ]
        if docker_tag not in tags_of_image:
            echo(
                "The running docker container is not \
                                the tag you requested!"
            )
            echo(
                "please stop first with docker stop {}".format(
                    my_node.btcd_container.id
                )
            )
            sys.exit(1)
        echo(f"containerImage: {my_node.btcd_container.image.tags} ")
    echo(f"           url: {my_node.rpcconn.render_url()}")
    echo(f"user, password: { my_node.rpcconn.rpcuser }, secret")
    echo(f"    host, port: localhost, {my_node.rpcconn.rpcport}")
    echo(
        f"   {node_impl}-cli: {node_impl}-cli -regtest -rpcport={my_node.rpcconn.rpcport} -rpcuser={ my_node.rpcconn.rpcuser } -rpcpassword=secret getblockchaininfo "
    )

    if create_conn_json:
        conn = my_node.rpcconn.as_data()
        conn["pid"] = os.getpid()  # usefull to send signals
        conn["specter_data_folder"] = config_obj[
            "SPECTER_DATA_FOLDER"
        ]  # e.g. cypress might want to know where we're mining to
        conn[f"{node_impl}_data_dir"] = data_dir
        conn_file = f"{'btcd' if node_impl == 'bitcoin' else 'elmd'}-conn.json"
        with open(conn_file, "w") as file:
            file.write(json.dumps(conn))

        def cleanup():
            os.remove(conn_file)

        atexit.register(cleanup)

    signal.signal(
        signal.SIGUSR1,
        lambda x, y: mine_2_specter_wallets(
            node_impl, my_node, config_obj["SPECTER_DATA_FOLDER"], echo
        ),
    )

    if node_impl == "elements":
        prepare_elements_default_wallet(my_node)

    if mining:
        miner_loop(
            node_impl,
            my_node,
            config_obj["SPECTER_DATA_FOLDER"],
            mining_every_x_seconds,
            echo,
        )


def prepare_elements_default_wallet(my_node):
    """this will collect the free coins we have created with -initialfreecoins=2100000000000000
    and transfer them to the default-wallet
    """
    rpc = my_node.rpcconn.get_rpc()
    wallet = rpc.wallet("")
    freehash = rpc.getblockhash(0)
    freetxid = rpc.getblock(freehash)["tx"][1]
    logger.debug(f"freetxid: {freetxid}")
    if rpc.gettxout(freetxid, 0):  # unspent!
        tx = rpc.getrawtransaction(freetxid, 1)
        fee = 1000e-8
        value = round(tx["vout"][0]["value"] - fee, 8)
        addr = wallet.getnewaddress()
        unconfidential = wallet.getaddressinfo(addr)["unconfidential"]
        rawtx = wallet.createrawtransaction(
            [{"txid": freetxid, "vout": 0}],  # inputs
            [{unconfidential: value}, {"fee": fee}],
        )
        wallet.sendrawtransaction(rawtx)
        rpc.generatetoaddress(101, unconfidential)


def miner_loop(node_impl, my_node, data_folder, mining_every_x_seconds, echo):
    "An endless loop mining bitcoin"

    echo(
        "Now, mining a block every %f seconds, avoid it via --no-mining"
        % mining_every_x_seconds
    )
    mine_2_specter_wallets(node_impl, my_node, data_folder, echo)

    # make them spendable
    my_node.mine(block_count=100)
    echo(
        f"height: {my_node.rpcconn.get_rpc().getblockchaininfo()['blocks']} | ",
        nl=False,
    )
    i = 0
    while True:
        try:
            my_node.mine()
            current_height = my_node.rpcconn.get_rpc().getblockchaininfo()["blocks"]
        except Exception as e:
            logger.debug(
                f"Caught {e}, Couldn't mine, assume SIGTERM occured => exiting!"
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


def mine_2_specter_wallets(node_impl, my_node, data_folder, echo):
    """Get each specter-wallet some coins"""

    from ..process_controller.node_controller import fetch_wallet_addresses_for_mining

    try:

        for address in fetch_wallet_addresses_for_mining(node_impl, data_folder):
            echo("")
            echo(f"Mining to address {address}")
            my_node.testcoin_faucet(address)
            # my_node.mine(address=address)
        # my_node.mine(block_count=100)
    except FileNotFoundError:
        # might happen if there no ~/.specter folder yet
        pass

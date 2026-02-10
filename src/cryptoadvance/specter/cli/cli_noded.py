import atexit
import json
import logging
import os
import shutil
import signal
import sys
import time
from pathlib import Path
from threading import Event
from xmlrpc.client import Boolean

import click
import psutil
from flask import Config
from requests.exceptions import ConnectionError

from ..config import DEFAULT_CONFIG
from ..process_controller.elementsd_controller import ElementsPlainController
from ..process_controller.node_controller import find_node_executable
from .utils import (
    Echo,
    compute_data_dir_and_set_config_obj,
    kill_node_process,
    purge_node_data_dir,
)

logger = logging.getLogger(__name__)

# ------------------------bitcoind -----------------------------------------------------


@click.command()
@click.option("--quiet/--no-quiet", default=False, help="Output as little as possible.")
@click.option(
    "--data-dir",
    help="Specify a (maybe not yet existing) datadir. Works only with --nodocker. (Default is /tmp/bitcoind_plain_datadir)",
)
@click.option(
    "--port",
    default=18443,
    help="Specify a port the Bitcoind should run on. Default is 18443.",
)
@click.option(
    "--log-stdout",
    is_flag=True,
    default=False,
    help="Will spit out logs on stdout if set",
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
    data_dir,
    port,
    log_stdout,
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
        data_dir,
        port,
        log_stdout,
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
    "--port",
    default=18884,
    help="Specify a port the elementsd should run on. Default is 18884.",
)
@click.option(
    "--log-stdout",
    is_flag=True,
    default=False,
    help="Will spit out logs on stdout if set",
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
    port,
    log_stdout,
    mining,
    mining_period,
    reset,
    create_conn_json,
    cleanuphard,
    config,
):
    """This will start a elements regtest and mines a block every mining-period.
    If a bitcoind is already running on port 18443, it won't start another one. If you CTRL-C this, the bitcoind will
    still continue to run. You have to shut it down.
    """
    noded(
        "elements",
        quiet,
        data_dir,
        port,
        log_stdout,
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
    data_dir,
    port,
    log_stdout,
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
        did_something = kill_node_process(node_impl, echo)
        did_something = (
            purge_node_data_dir(node_impl, config_obj, echo) or did_something
        )
        if not did_something:
            echo("Nothing to do!")
        return
    mining_every_x_seconds = float(mining_period)
    echo(f"Creating plain {node_impl}d")
    if node_impl == "bitcoin":
        my_node = BitcoindPlainController(
            bitcoind_path=find_node_executable("bitcoin"), rpcport=port
        )
    elif node_impl == "elements":
        my_node = ElementsPlainController(
            elementsd_path=find_node_executable("elements"), rpcport=port
        )
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    try:
        echo(f"Starting {node_impl}d")
        if node_impl == "bitcoin":
            my_node.start_bitcoind(
                cleanup_at_exit=True,
                cleanup_hard=cleanuphard,
                datadir=data_dir,
                log_stdout=log_stdout,
            )
        elif node_impl == "elements":
            my_node.start_elementsd(
                cleanup_at_exit=True,
                cleanup_hard=cleanuphard,
                datadir=data_dir,
                log_stdout=log_stdout,
            )
    except Exception as e:
        if str(e).startswith("There is already a node running!"):
            echo(f"{e} please reset via:")
            echo(f"python3 -m cryptoadvance.specter {node_impl}d --reset")
        else:
            raise e
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
    # Mining/NOP loop (necessary to keep the Python process running)
    endless_loop(
        node_impl,
        my_node,
        mining,
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


def endless_loop(
    node_impl, my_node, mining: Boolean, data_folder, mining_every_x_seconds, echo
):
    """This loop can enable continuous mining"""

    # To stop the Python process
    exit = Event()

    def exit_now(signum, frame):
        echo(f"Signal {signum} received. Terminating the Python process. Bye, bye!")
        exit.set()

    signal.signal(signal.SIGINT, exit_now)
    signal.signal(signal.SIGHUP, exit_now)
    signal.signal(signal.SIGTERM, exit_now)
    # SIGKILL cannot be caught

    if mining:
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
    else:
        echo("Press Ctrl-C to abort and stop the node")

    prevent_mining_file = Path("prevent_mining")
    i = 0
    while not exit.is_set():
        try:
            current_height = my_node.rpcconn.get_rpc().getblockchaininfo()["blocks"]
            exit.wait(mining_every_x_seconds)
            # Having a prevent_mining_file overrides the mining cli option
            if mining and not prevent_mining_file.is_file():
                my_node.mine()
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
            elif mining:
                echo("X", prefix=False, nl=False)
                continue

        except ConnectionError as nce:
            # This terminates the Python processes if the bitcoind / elementsd (child) processes are somehow terminated
            echo("Exiting endless loop due to lost RPC connection.")
            break
        except Exception as e:
            logger.debug(
                f"Caught {e.__module__}, Couldn't mine, assume SIGTERM occurred => exiting!"
            )
            break
    if prevent_mining_file.is_file():
        echo("Deleting file prevent_mining")
        prevent_mining_file.unlink()
    echo(f"THE_END(@height:{current_height})")


def mine_2_specter_wallets(node_impl, my_node, data_folder, echo):
    """Sending coins to all Specter wallets, except for "Fresh wallet" which is not supposed to have any tx"""

    from ..process_controller.node_controller import fetch_wallet_addresses_for_mining

    # Using the dict key, not the wallet name
    exception = "fresh_wallet"
    try:
        logger.debug(f"Funding wallets in {data_folder}/wallets")
        for address in fetch_wallet_addresses_for_mining(
            node_impl, data_folder, exception
        ):
            echo(f"Mining to address {address}")
            my_node.testcoin_faucet(address)
    except FileNotFoundError:
        # might happen if there is no ~/.specter folder yet
        pass

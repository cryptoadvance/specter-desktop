import logging
from logging.config import dictConfig
import os
from os import path
import sys
import psutil
from pathlib import Path
import shutil
import time
from stem.control import Controller
from .util.tor import stop_hidden_services, start_hidden_service
import click

from .server import create_app, init_app
from .helpers import set_loglevel

import signal

logger = logging.getLogger(__name__)


@click.group()
def cli():
    pass


@cli.command()
@click.option("--daemon", is_flag=True)
@click.option("--stop", is_flag=True)
@click.option("--restart", is_flag=True)
@click.option("--force", is_flag=True)
# options below can help to run it on a remote server,
# but better use nginx
@click.option("--port")  # default - 25441 set to 80 for http, 443 for https
# set to 0.0.0.0 to make it available outside
@click.option("--host", default="127.0.0.1")
# for https:
@click.option("--cert")
@click.option("--key")
@click.option("--debug/--no-debug", default=None)
@click.option("--tor", is_flag=True)
@click.option("--hwibridge", is_flag=True)
def server(daemon, stop, restart, force, port, host, cert, key, debug, tor, hwibridge):
    # create an app to get Specter instance
    # and it's data folder
    logger.info("Logging is hopefully configured")
    if debug:
        ca_logger = logging.getLogger("cryptoadvance")
        ca_logger.setLevel(logging.DEBUG)
        logger.debug("We're now on level DEBUG on logger cryptoadvance")
    app = create_app()
    app.app_context().push()
    init_app(app, hwibridge=hwibridge)

    # we will store our daemon PID here
    pid_file = path.join(app.specter.data_folder, "daemon.pid")
    toraddr_file = path.join(app.specter.data_folder, "onion.txt")
    # check if pid file exists
    if path.isfile(pid_file):
        # if we need to stop daemon
        if stop or restart:
            print("Stopping the Specter server...")
            with open(pid_file) as f:
                pid = int(f.read())
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.3)
            try:
                os.remove(pid_file)
            except Exception:
                pass
        elif daemon:
            if not force:
                print(
                    f'PID file "{pid_file}" already exists. \
                        Use --force to overwrite'
                )
                return
            else:
                os.remove(pid_file)
        if stop:
            return
    else:
        if stop or restart:
            print(f'Can\'t find PID file "{pid_file}"')
            if stop:
                return

    # watch templates folder to reload when something changes
    extra_dirs = ["templates"]
    extra_files = extra_dirs[:]
    for extra_dir in extra_dirs:
        for dirname, dirs, files in os.walk(extra_dir):
            for filename in files:
                filename = os.path.join(dirname, filename)
                if os.path.isfile(filename):
                    extra_files.append(filename)

    # if port is not defined - get it from environment
    if port is None:
        port = int(os.getenv("PORT", 25441))
    else:
        port = int(port)

    # certificates
    if cert is None:
        cert = os.getenv("CERT", None)
    if key is None:
        key = os.getenv("KEY", None)

    protocol = "http"
    kwargs = {"host": host, "port": port, "extra_files": extra_files}
    if cert is not None and key is not None:
        cert = os.path.abspath(cert)
        key = os.path.abspath(key)
        kwargs["ssl_context"] = (cert, key)
        protocol = "https"

    if hwibridge:
        print(
            " * Running HWI Bridge mode.\n"
            " * You can configure access to the API "
            "at: %s://%s:%d/hwi/settings" % (protocol, host, port)
        )

    # debug is false by default
    def run(debug=debug):
        try:
            app.controller = Controller.from_port()
        except Exception:
            app.controller = None
        try:
            port = 5000  # default flask port
            if "port" in kwargs:
                port = kwargs["port"]
            else:
                kwargs["port"] = port
            # if we have certificates
            if "ssl_context" in kwargs:
                tor_port = 443
            else:
                tor_port = 80
            app.port = port
            app.tor_port = tor_port
            app.save_tor_address_to = toraddr_file
            if debug and (tor or os.getenv("CONNECT_TOR") == "True"):
                print(
                    " * Warning: Cannot use Tor in debug mode. \
                      Starting in production mode instead."
                )
                debug = False
            if tor or os.getenv("CONNECT_TOR") == "True":
                try:
                    app.tor_enabled = True
                    start_hidden_service(app)
                except Exception as e:
                    print(f" * Failed to start Tor hidden service: {e}")
                    print(" * Continuing process with Tor disabled")
                    app.tor_service_id = None
                    app.tor_enabled = False
            else:
                app.tor_service_id = None
                app.tor_enabled = False
            app.run(debug=debug, **kwargs)
            stop_hidden_services(app)
        finally:
            if app.controller is not None:
                app.controller.close()

    # check if we should run a daemon or not
    if daemon or restart:
        print("Starting server in background...")
        print(" * Hopefully running on %s://%s:%d/" % (protocol, host, port))
        # macOS + python3.7 is buggy
        if sys.platform == "darwin" and (
            sys.version_info.major == 3 and sys.version_info.minor < 8
        ):
            print(
                " * WARNING: --daemon mode might not \
                   work properly in python 3.7 and lower \
                   on MacOS. Upgrade to python 3.8+"
            )
        from daemonize import Daemonize

        d = Daemonize(app="specter", pid=pid_file, action=run)
        d.start()
    else:
        # if not a daemon we can use DEBUG
        if debug is None:
            debug = app.config["DEBUG"]
        run(debug=debug)


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


@cli.command()
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
    default="/tmp/bitcoind_plain_datadir",
    help="specify a (maybe not yet existing) datadir. Works only in --nodocker (Default:/tmp/bitcoind_plain_datadir) ",
)
@click.option("--mining/--no-mining", default=True, help="Turns on mining (default)")
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
def bitcoind(
    debug, quiet, nodocker, docker_tag, data_dir, mining, mining_period, reset
):
    """This will start a bitcoind regtest and mines a block every mining-period.
    If a bitcoind is already running on port 18443, it won't start another one. If you CTRL-C this, the bitcoind will
    still continue to run. You have to shut it down.
    """
    # In order to avoid these dependencies for production use, we're importing them here:
    import docker
    from .bitcoind import (
        BitcoindDockerController,
        BitcoindPlainController,
        fetch_wallet_addresses_for_mining,
    )

    if debug:
        logging.getLogger("cryptoadvance").setLevel(logging.DEBUG)
        logger.debug("Now on debug-logging")
    echo = Echo(quiet).echo

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
                echo(f"Pid {pid} not owned by us. Might be a docker-process? {line}")
        if Path(data_dir).exists():
            echo(f"Purging Datadirectory {data_dir} ...")
            did_something = True
            shutil.rmtree(data_dir)
        if not did_something:
            echo("Nothing to do!")
        return
    logging.getLogger().setLevel(logging.INFO)
    mining_every_x_seconds = float(mining_period)
    if nodocker:
        echo("starting plain bitcoind")
        my_bitcoind = BitcoindPlainController()
        # Make sure datadir does exist if specified:
        Path(data_dir).mkdir(parents=True, exist_ok=True)
    else:
        echo("starting or detecting container")
        my_bitcoind = BitcoindDockerController(docker_tag=docker_tag)
    try:
        my_bitcoind.start_bitcoind(cleanup_at_exit=True, datadir=data_dir)
    except docker.errors.ImageNotFound:
        echo(f"Image with tag {docker_tag} does not exist!")
        echo(
            f"Try to download first with docker pull \
                     registry.gitlab.com/cryptoadvance/specter-desktop\
                     /python-bitcoind:{docker_tag}"
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
    if mining:
        echo(
            "Now, mining a block every %f seconds, avoid it via --no-mining"
            % mining_every_x_seconds
        )
        # Get each address some coins
        try:
            for address in fetch_wallet_addresses_for_mining():
                my_bitcoind.mine(address=address)
        except FileNotFoundError:
            # might happen if there no ~/.specter folder yet
            pass

        # make them spendable
        my_bitcoind.mine(block_count=100)
        echo(
            f"height: {my_bitcoind.rpcconn.get_rpc().getblockchaininfo()['blocks']} | ",
            nl=False,
        )
        i, j = 0, 0
        while True:
            my_bitcoind.mine()
            echo("%i" % (i % 10), prefix=False, nl=False)
            if i % 10 == 9:
                echo(" ", prefix=False, nl=False)
            i += 1
            if i >= 50:
                j = i
                i = 0
                echo("", prefix=False)
                echo(
                    f"height: {my_bitcoind.rpcconn.get_rpc().getblockchaininfo()['blocks']} | ",
                    nl=False,
                )
            time.sleep(mining_every_x_seconds)

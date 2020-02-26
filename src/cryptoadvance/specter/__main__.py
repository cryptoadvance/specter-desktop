import atexit
import logging
import os
import sys
import time

import click

import docker

from .bitcoind import (BitcoindDockerController,
                       fetch_wallet_addresses_for_mining)
from .helpers import load_jsons, which
from .server import DATA_FOLDER, create_app, init_app

from daemonize import Daemonize
from os import path
import signal

DEBUG = True

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
@click.option("--port") # default - 25441 set to 80 for http, 443 for https
@click.option("--host", default="127.0.0.1") # set to 0.0.0.0 to make it available outside
# for https:
@click.option("--cert")
@click.option("--key")
# provide tor password here
@click.option("--tor")
def server(daemon, stop, restart, force, port, host, cert, key, tor):
    # we will store our daemon PIN here
    pid_file = path.expanduser(path.join(DATA_FOLDER, "daemon.pid"))
    toraddr_file = path.expanduser(path.join(DATA_FOLDER, "onion.txt"))
    # check if pid file exists
    if path.isfile(pid_file):
        # if we need to stop daemon
        if stop or restart:
            print("Stopping the Specter server...")
            with open(pid_file) as f:
                pid = int(f.read())
            os.kill(pid, signal.SIGTERM)
        elif daemon:
            if not force:
                print(f"PID file \"{pid_file}\" already exists. Use --force to overwrite")
                return
        if stop:
            return
    else:
        if stop or restart:
            print(f"Can't find PID file \"{pid_file}\"")
            if stop:
                return

    app = create_app()
    app.app_context().push()
    init_app(app)

    # watch templates folder to reload when something changes
    extra_dirs = ['templates']
    extra_files = extra_dirs[:]
    for extra_dir in extra_dirs:
        for dirname, dirs, files in os.walk(extra_dir):
            for filename in files:
                filename = os.path.join(dirname, filename)
                if os.path.isfile(filename):
                    extra_files.append(filename)
    
    # if port is not defined - get it from environment
    if port is None:
        port = int(os.getenv('PORT', 25441))
    else:
        port = int(port)

    # certificates
    if cert is None:
        cert = os.getenv('CERT', None)
    if key is None:
        key = os.getenv('KEY', None)

    protocol = "http"
    kwargs = {
        "host": host,
        "port": port,
        "extra_files": extra_files,
    }
    if cert is not None and key is not None:
        cert = os.path.abspath(cert)
        key = os.path.abspath(key)
        kwargs["ssl_context"] = (cert, key)
        protocol = "https"

    # if tor password is not provided but env variable is set
    if tor is None and os.getenv('CONNECT_TOR') == 'True':
        from dotenv import load_dotenv
        load_dotenv()   # Load the secrets from .env
        tor = os.getenv('TOR_PASSWORD')

    def run(debug=False):
        # Note: dotenv doesn't convert bools!
        if tor is not None:
            from . import tor_util
            # if we have certificates
            if "ssl_context" in kwargs:
                tor_port = 443
            else:
                tor_port = 80
            tor_util.run_on_hidden_service(app,
                debug=False,
                tor_password=tor,
                tor_port=tor_port,
                save_address_to=toraddr_file,
                **kwargs)
        else:
            app.run(debug=debug, **kwargs)

    # check if we should run a daemon or not
    if daemon or restart:
        print("Starting server in background...")
        print("* Hopefully running on %s://%s:%d/" % (protocol, host, port))
        if tor is not None:
            print("* For onion address check the file %s" % toraddr_file)
        # Note: we can't run flask as a deamon in debug mode,
        #       so use debug=False by default
        d = Daemonize(app="specter", pid=pid_file, action=run)
        d.start()
    # if not a daemon we can use DEBUG
    else:
        run(DEBUG)

@cli.command()
@click.option('--debug/--no-debug', default=False)
@click.option('--mining/--no-mining', default=True)
@click.option('--docker-tag', "docker_tag", default="latest")
def bitcoind(debug,mining, docker_tag):
    mining_every_x_seconds = 15
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    click.echo("    --> starting or detecting container")
    my_bitcoind = BitcoindDockerController(docker_tag=docker_tag)
    try:
        my_bitcoind.start_bitcoind()
    except docker.errors.ImageNotFound:
        click.echo("    --> Image with tag {} does not exist!".format(docker_tag))
        click.echo("    --> Try to download first with docker pull registry.gitlab.com/cryptoadvance/specter-desktop/python-bitcoind:{}".format(docker_tag))
        sys.exit(1)
    tags_of_image = [ image.split(":")[-1]  for image in my_bitcoind.btcd_container.image.tags]
    if not docker_tag in tags_of_image:
        click.echo("    --> The running docker container is not the tag you requested!")
        click.echo("    --> please stop first with docker stop {}".format(my_bitcoind.btcd_container.id))
        sys.exit(1)
    click.echo("    --> containerImage: %s" % my_bitcoind.btcd_container.image.tags)
    click.echo("    -->            url: %s" % my_bitcoind.rpcconn.render_url())
    click.echo("    --> user, password: bitcoin, secret")
    click.echo("    -->     host, port: localhost, 18443")
    click.echo("    -->    bitcoin-cli: bitcoin-cli -regtest -rpcuser=bitcoin -rpcpassword=secret getblockchaininfo ")
    if mining:
        click.echo("    --> Now, mining a block every %i seconds. Avoid it via --no-mining" % mining_every_x_seconds)
        # Get each address some coins
        try:
            for address in fetch_wallet_addresses_for_mining():
                my_bitcoind.mine(address=address)
        except FileNotFoundError:
            # might happen if there no ~/.specter folder yet
            pass

        # make them spendable
        my_bitcoind.mine(block_count=100)
        click.echo("    --> ",nl=False)
        i = 0
        while True:
            my_bitcoind.mine()
            click.echo("%i"% (i%10),nl=False)
            if i%10 == 9:
                click.echo(" ",nl=False)
            i += 1
            if i >= 50:
                i=0
                click.echo(" ")
                click.echo("    --> ",nl=False)
            time.sleep(mining_every_x_seconds)



if __name__ == "__main__":
    cli()
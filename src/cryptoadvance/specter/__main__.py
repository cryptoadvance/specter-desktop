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

DEBUG = True

@click.group()
def cli():
    pass


@cli.command()
def server():
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
    
    # Note: dotenv doesn't convert bools!
    if os.getenv('CONNECT_TOR', 'False') == 'True' and os.getenv('TOR_PASSWORD') is not None:
        import tor_util
        tor_util.run_on_hidden_service(
            app, port=os.getenv('PORT'), 
            debug=DEBUG, extra_files=extra_files
        )
    else:
        app.run(port=os.getenv('PORT'), debug=DEBUG, extra_files=extra_files)

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

''' Stuff to control a bitcoind-instance. Either directly by access to a bitcoind-executable or
    via docker.
'''
import os
import atexit
import logging
import shutil
import subprocess
import tempfile
import time

import click
import docker
from bitcoind import BitcoindDockerController
from server import DATA_FOLDER
from helpers import which, load_jsons


@click.group()
def cli():
    pass

@cli.command()
@click.option('--debug/--no-debug', default=False)
@click.option('--mining/--no-mining', default=True)
def bitcoind(debug,mining):
    mining_every_x_seconds = 15
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    click.echo("    --> starting or detecting container")
    my_bitcoind = BitcoindDockerController()
    my_bitcoind.start_bitcoind()
    click.echo("    --> containerId: %s" % my_bitcoind.btcd_container.id)
    click.echo("    -->         url: %s" % my_bitcoind.rpcconn.render_url())
    if mining:
        click.echo("    --> Now, mining a block every %i seconds. Avoid it via --no-mining" % mining_every_x_seconds)
        # Get each address some coins
        for address in fetch_wallet_addresses_for_mining():
            my_bitcoind.mine(address=address)
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

def fetch_wallet_addresses_for_mining(data_folder=None):
    ''' parses all the wallet-jsons in the folder (default ~/.specter/wallets/regtest)
        and returns an array with the addresses 
    '''
    if data_folder == None:
        data_folder = os.path.expanduser(DATA_FOLDER)
    wallets = load_jsons(data_folder+"/wallets/regtest")
    address_array = [ value['address'] for key, value in wallets.items()]
    # remove duplicates
    address_array = list( dict.fromkeys(address_array) )
    return address_array




if __name__ == "__main__":
    cli()

import atexit
import logging
from logging.config import dictConfig
import os
import sys
import time

import click

import docker

from cryptoadvance.specter.bitcoind import (BitcoindDockerController,
                       fetch_wallet_addresses_for_mining)
from cryptoadvance.specter.helpers import which
from cryptoadvance.specter.server import DATA_FOLDER, create_app, init_app
import cryptoadvance.specter.config

from os import path
import signal

def server(daemon=False, stop=False, restart=False, force=False, 
           port=25441, host="127.0.0.1", cert=None, key=None, tor=None, 
           hwibridge=False):
    print("Starting Specter server... It may take a bit, please be patient.")
    # we will store our daemon PID here
    pid_file = path.expanduser(path.join(DATA_FOLDER, "daemon.pid"))
    toraddr_file = path.expanduser(path.join(DATA_FOLDER, "onion.txt"))

    app = create_app()
    app.app_context().push()
    init_app(app, hwibridge=hwibridge)

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
    }

    app.run(debug=False, **kwargs)

if __name__ == "__main__":
    # central and early configuring of logging
    # see https://flask.palletsprojects.com/en/1.1.x/logging/#basic-configuration
    dictConfig({
        'version': 1,
        'formatters': {'default': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        }},
        'handlers': {'wsgi': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://flask.logging.wsgi_errors_stream',
            'formatter': 'default'
        }},
        'root': {
            'level': 'INFO',
            'handlers': ['wsgi']
        }
    })
    server()
import sys, json, os, time, base64
import requests
import random, copy
from collections import OrderedDict
from threading import Thread

from flask import Flask, Blueprint, render_template, request, redirect, jsonify
from flask_qrcode import QRcode

from helpers import normalize_xpubs, run_shell
from descriptor import AddChecksum
from rpc import BitcoinCLI, RPC_PORTS

from specter import Specter, purposes, addrtypes
from datetime import datetime
import urllib

from pathlib import Path
env_path = Path('.') / '.flaskenv'
from dotenv import load_dotenv
load_dotenv(env_path)

DEBUG = True


if getattr(sys, 'frozen', False):
    template_folder = os.path.join(os.path.realpath(__file__), 'templates')
    static_folder = os.path.join(os.path.realpath(__file__), 'static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    app = Flask(__name__, template_folder="templates", static_folder="static")
QRcode(app) # enable qr codes generation


DATA_FOLDER = "~/.specter"

MSIG_TYPES = {
    "legacy": "P2SH",
    "p2sh-segwit": "P2SH_P2WSH",
    "bech32": "P2WSH"
}
SINGLE_TYPES = {
    "legacy": "P2PKH",
    "p2sh-segwit": "P2SH_P2WPKH",
    "bech32": "P2WPKH"
}



from views.hwi import hwi_views
app.register_blueprint(hwi_views, url_prefix='/hwi')
with app.app_context():
    import controller



############### startup ##################

if __name__ == '__main__':
    specter = Specter(DATA_FOLDER)
    specter.check()

    # Attach specter instance so child views (e.g. hwi) can access it
    app.specter = specter

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
        tor_util.run_on_hidden_service(app, port=os.getenv('PORT'), debug=DEBUG, extra_files=extra_files)
    else:
        app.run(port=os.getenv('PORT'), debug=DEBUG, extra_files=extra_files)




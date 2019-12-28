import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from flask_qrcode import QRcode

from descriptor import AddChecksum
from specter import Specter
from views.hwi import hwi_views

env_path = Path('.') / '.flaskenv'
load_dotenv(env_path)

DEBUG = True

def create_app():
    if getattr(sys, 'frozen', False):
        template_folder = os.path.join(os.path.realpath(__file__), 'templates')
        static_folder = os.path.join(os.path.realpath(__file__), 'static')
        app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
    else:
        app = Flask(__name__, template_folder="templates", static_folder="static")
    QRcode(app) # enable qr codes generation
    specter = Specter(DATA_FOLDER)
    specter.check()
    # Attach specter instance so child views (e.g. hwi) can access it
    app.specter = specter
    app.register_blueprint(hwi_views, url_prefix='/hwi')
    with app.app_context():
        import controller
    return app


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




############### startup ##################

if __name__ == '__main__':
    app = create_app()
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

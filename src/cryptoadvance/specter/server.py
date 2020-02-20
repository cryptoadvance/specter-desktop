import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from flask_qrcode import QRcode
from flask_login import LoginManager, login_user

from .descriptor import AddChecksum
from .logic import Specter
from .views.hwi import hwi_views

env_path = Path('.') / '.flaskenv'
load_dotenv(env_path)


def create_app(config="cryptoadvance.specter.config.DevelopmentConfig"):
    # Enables injection of a different config via Env-Variable
    if os.environ.get("SPECTER_CONFIG"):
        config = os.environ.get("SPECTER_CONFIG")

    if getattr(sys, 'frozen', False):

        # Best understood with the snippet below this section:
        # https://pyinstaller.readthedocs.io/en/v3.3.1/runtime-information.html#using-sys-executable-and-sys-argv-0
        template_folder = os.path.join(sys._MEIPASS, 'templates')
        static_folder = os.path.join(sys._MEIPASS, 'static')
        logging.info("pyinstaller based instance running in {}".format(sys._MEIPASS))
        app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
    else:
        app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config)
    return app


def init_app(app):
    '''  see blogpost 19nd Feb 2020 '''
    QRcode(app) # enable qr codes generation
    # Login via Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app) # Enable Login
    login_manager.login_view = "login" # Enable redirects if unauthorized
    @login_manager.user_loader
    def load_user(user_id):
        return AuthenticatedUser()
    # let's make it a bit more convenient
    def login():
        login_user(load_user(""))
    
    app.login = login

    specter = Specter(DATA_FOLDER)
    specter.check()
    # Attach specter instance so child views (e.g. hwi) can access it
    app.specter = specter
    app.register_blueprint(hwi_views, url_prefix='/hwi')
    with app.app_context():
        from . import controller
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

class AuthenticatedUser:
    ''' A minimal implementation implementing the User Class needed for Flask-Login '''
    
    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return "there-is-only-one-User"
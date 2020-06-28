import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, redirect
from flask_login import LoginManager, login_user

from .helpers import hwi_get_config
from .specter import Specter
from .hwi_server import hwi_server
from .user import User

logger = logging.getLogger(__name__)

env_path = Path('.') / '.flaskenv'
load_dotenv(env_path)

DATA_FOLDER = "~/.specter"

def create_app(config="cryptoadvance.specter.config.DevelopmentConfig"):
    # Enables injection of a different config via Env-Variable
    if os.environ.get("SPECTER_CONFIG"):
        config = os.environ.get("SPECTER_CONFIG")

    if getattr(sys, 'frozen', False):

        # Best understood with the snippet below this section:
        # https://pyinstaller.readthedocs.io/en/v3.3.1/runtime-information.html#using-sys-executable-and-sys-argv-0
        template_folder = os.path.join(sys._MEIPASS, 'templates')
        static_folder = os.path.join(sys._MEIPASS, 'static')
        logger.info("pyinstaller based instance running in {}".format(sys._MEIPASS))
        app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
    else:
        app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config)
    return app


def init_app(app, hwibridge=False, specter=None):
    '''  see blogpost 19nd Feb 2020 '''
    app.logger.info("Initializing QRcode")
    # Login via Flask-Login
    app.logger.info("Initializing LoginManager")
    if specter == None:
        # the default. If not None, then it got injected for testing
        app.logger.info("Initializing Specter")
        specter = Specter(DATA_FOLDER)

    login_manager = LoginManager()
    login_manager.init_app(app) # Enable Login
    login_manager.login_view = "login" # Enable redirects if unauthorized
    @login_manager.user_loader
    def user_loader(id):
        return User.get_user(specter, id)

    def login(id):
        login_user(user_loader(id))
    
    app.login = login
    # Attach specter instance so child views (e.g. hwi) can access it
    app.specter = specter
    if specter.config.get('auth') == "none":
        app.logger.info("Login disabled")
        app.config["LOGIN_DISABLED"] = True
    else:
        app.logger.info("Login enabled")
    app.logger.info("Initializing Controller ...")
    app.register_blueprint(hwi_server, url_prefix='/hwi')
    if not hwibridge:
        with app.app_context():
            from cryptoadvance.specter import controller
            if app.config.get("TESTING") and len(app.view_functions) <=3 :
                # Need to force a reload as otherwise the import is skipped
                # in pytest, the app is created anew for ech test
                # But we shouldn't do that if not necessary as this would result in
                # --> View function mapping is overwriting an existing endpoint function
                import importlib
                importlib.reload(controller)
    else:
        @app.route("/", methods=["GET"])
        def index():
            return redirect('/hwi/settings')
    return app

def create_and_init():
    ''' This method can be used to fill the FLASK_APP-env variable like
        export FLASK_APP="src/cryptoadvance/specter/server:create_and_init()"
        See Development.md to use this for debugging
    '''
    app = create_app()
    app.app_context().push()
    init_app(app)
    return app

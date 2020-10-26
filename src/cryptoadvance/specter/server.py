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
from .config import DATA_FOLDER
from .util.version import VersionChecker

from werkzeug.middleware.proxy_fix import ProxyFix

logger = logging.getLogger()

env_path = Path(".") / ".flaskenv"
load_dotenv(env_path)


def create_app(config="cryptoadvance.specter.config.DevelopmentConfig"):
    # Enables injection of a different config via Env-Variable
    if os.environ.get("SPECTER_CONFIG"):
        config = os.environ.get("SPECTER_CONFIG")

    if getattr(sys, "frozen", False):

        # Best understood with the snippet below this section:
        # https://pyinstaller.readthedocs.io/en/v3.3.1/runtime-information.html#using-sys-executable-and-sys-argv-0
        template_folder = os.path.join(sys._MEIPASS, "templates")
        static_folder = os.path.join(sys._MEIPASS, "static")
        logger.info("pyinstaller based instance running in {}".format(sys._MEIPASS))
        app = Flask(
            __name__, template_folder=template_folder, static_folder=static_folder
        )
    else:
        app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config)
    app.wsgi_app = ProxyFix(
        app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1
    )
    return app


def init_app(app, hwibridge=False, specter=None):
    """  see blogpost 19nd Feb 2020 """
    # Login via Flask-Login
    app.logger.info("Initializing LoginManager")
    if specter is None:
        # the default. If not None, then it got injected for testing
        app.logger.info("Initializing Specter")
        specter = Specter(DATA_FOLDER)

    # version checker
    # checks for new versions once per hour
    specter.version = VersionChecker()
    specter.version.start()

    login_manager = LoginManager()
    login_manager.init_app(app)  # Enable Login
    login_manager.login_view = "login"  # Enable redirects if unauthorized

    @login_manager.user_loader
    def user_loader(id):
        return specter.user_manager.get_user(id)

    def login(id):
        login_user(user_loader(id))

    app.login = login
    # Attach specter instance so child views (e.g. hwi) can access it
    app.specter = specter
    if specter.config.get("auth") == "none":
        app.logger.info("Login disabled")
        app.config["LOGIN_DISABLED"] = True
    else:
        app.logger.info("Login enabled")
    app.logger.info("Initializing Controller ...")
    app.register_blueprint(hwi_server, url_prefix="/hwi")
    if not hwibridge:
        with app.app_context():
            from cryptoadvance.specter import controller

            if app.config.get("TESTING") and len(app.view_functions) <= 20:
                # Need to force a reload as otherwise the import is skipped
                # in pytest, the app is created anew for ech test
                # But we shouldn't do that if not necessary as this would result in
                # --> View function mapping is overwriting an existing endpoint function
                # see archblog for more about this nasty workaround
                import importlib

                importlib.reload(controller)
    else:

        @app.route("/", methods=["GET"])
        def index():
            return redirect("/hwi/settings")

    @app.context_processor
    def inject_tor():
        if app.config["DEBUG"]:
            return dict(tor_service_id="", tor_enabled=False)
        return dict(tor_service_id=app.tor_service_id, tor_enabled=app.tor_enabled)

    return app


def create_and_init():
    """This method can be used to fill the FLASK_APP-env variable like
    export FLASK_APP="src/cryptoadvance/specter/server:create_and_init()"
    See Development.md to use this for debugging
    """
    app = create_app()
    app.app_context().push()
    init_app(app)
    return app

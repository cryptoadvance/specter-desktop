import logging
import os
import sys
import secrets
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, redirect, url_for
from flask_login import LoginManager, login_user
from flask_wtf.csrf import CSRFProtect

from .helpers import hwi_get_config
from .specter import Specter
from .hwi_server import hwi_server
from .user import User
from .util.version import VersionChecker

from werkzeug.middleware.proxy_fix import ProxyFix
from jinja2 import select_autoescape

logger = logging.getLogger(__name__)

env_path = Path(".") / ".flaskenv"
load_dotenv(env_path)

csrf = CSRFProtect()


def calc_module_name(config):
    """ tiny helper to make passing configs more convenient """
    if "." in config:
        return config
    else:
        return "cryptoadvance.specter.config." + config


def create_app(config=None):

    # Cmdline has precedence over Env-Var
    if config is not None:
        config = calc_module_name(
            os.environ.get("SPECTER_CONFIG")
            if os.environ.get("SPECTER_CONFIG")
            else config
        )
    else:
        # Enables injection of a different config via Env-Variable
        if os.environ.get("SPECTER_CONFIG"):
            config = calc_module_name(os.environ.get("SPECTER_CONFIG"))
        else:
            # Default
            config = "cryptoadvance.specter.config.ProductionConfig"

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
    app.jinja_env.autoescape = select_autoescape(default_for_string=True, default=True)
    logger.info(f"Configuration: {config}")
    app.config.from_object(config)
    app.wsgi_app = ProxyFix(
        app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1
    )
    csrf.init_app(app)
    app.csrf = csrf
    return app


def init_app(app, hwibridge=False, specter=None):
    """  see blogpost 19nd Feb 2020 """
    # Login via Flask-Login
    app.logger.info("Initializing LoginManager")
    app.secret_key = app.config["SECRET_KEY"]
    if specter is None:
        # the default. If not None, then it got injected for testing
        app.logger.info("Initializing Specter")
        specter = Specter(
            data_folder=app.config["SPECTER_DATA_FOLDER"],
            config=app.config["DEFAULT_SPECTER_CONFIG"],
        )

    # version checker
    # checks for new versions once per hour
    specter.version = VersionChecker(specter=specter)
    specter.version.start()

    login_manager = LoginManager()
    login_manager.session_protection = "strong"
    login_manager.init_app(app)  # Enable Login
    login_manager.login_view = "auth_endpoint.login"  # Enable redirects if unauthorized
    app.config["SESSION_COOKIE_SAMESITE"] = "Strict"

    @login_manager.user_loader
    def user_loader(id):
        return specter.user_manager.get_user(id)

    def login(id):
        login_user(user_loader(id))

    app.login = login
    # Attach specter instance so child views (e.g. hwi) can access it
    app.specter = specter
    if specter.config["auth"].get("method") == "none":
        app.logger.info("Login disabled")
        app.config["LOGIN_DISABLED"] = True
    else:
        app.logger.info("Login enabled")
    app.logger.info("Initializing Controller ...")
    app.register_blueprint(hwi_server, url_prefix="/hwi")
    csrf.exempt(hwi_server)
    if not hwibridge:
        with app.app_context():
            from cryptoadvance.specter.server_endpoints import controller

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
            return redirect(url_for("hwi_server.hwi_bridge_settings"))

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

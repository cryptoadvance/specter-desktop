import logging
import os
import sys
from distutils.core import setup
from http.client import HTTPConnection
from pathlib import Path

from cryptoadvance.specter.liquid.rpc import LiquidRPC
from cryptoadvance.specter.managers.service_manager import ExtensionManager
from cryptoadvance.specter.rpc import BitcoinRPC
from cryptoadvance.specter.services import callbacks
from cryptoadvance.specter.util.reflection import get_template_static_folder
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, request, session, url_for
from flask_apscheduler import APScheduler
from flask_login import LoginManager, login_user
from flask_wtf.csrf import CSRFProtect
from jinja2 import select_autoescape
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.wrappers import Response

from cryptoadvance.specter.hwi_rpc import HWIBridge
from cryptoadvance.specter.liquid.rpc import LiquidRPC
from cryptoadvance.specter.managers.service_manager import ExtensionManager
from cryptoadvance.specter.rpc import BitcoinRPC
from cryptoadvance.specter.services import callbacks
from cryptoadvance.specter.util.reflection import get_template_static_folder

from .htmlsafebabel import HTMLSafeBabel
from .hwi_server import hwi_server
from .services.callbacks import after_serverpy_init_app, specter_added_to_flask_app
from .specter import Specter
from .util.specter_migrator import SpecterMigrator

logger = logging.getLogger(__name__)

env_path = Path(".") / ".flaskenv"
load_dotenv(env_path)

csrf = CSRFProtect()


class SpecterFlask(Flask):
    @property
    def supported_languages(self):
        return self.config["LANGUAGES"]

    def get_language_code(self):
        """
        Helper for Babel and other related language selection tasks.
        """
        try:
            if "language_code" in session:
                # Explicit selection
                return session["language_code"]
            else:
                # autodetect
                return request.accept_languages.best_match(
                    self.supported_languages.keys()
                )
        except:  # RuntimeError: Working outside of request context.
            return "en"

    def set_language_code(self, language_code):
        session["language_code"] = language_code
        session["is_language_rtl"] = language_code in self.config["RTL_LANGUAGES"]


def calc_module_name(config):
    """tiny helper to make passing configs more convenient"""
    if "." in config:
        return config
    else:
        return "cryptoadvance.specter.config." + config


def create_app(config=None):
    """config is either a string:
    * if it's with dots, it's fqn classname
    * without dots cryptoadvance.specter.config will be added in the front
    ir it's a class directly. Then it's simply passed through
    """
    # Cmdline has precedence over Env-Var
    if config is not None:
        if isinstance(config, str):
            config = calc_module_name(
                os.environ.get("SPECTER_CONFIG")
                if os.environ.get("SPECTER_CONFIG")
                else config
            )
            config_name = config
        elif isinstance(config, type):
            # Useful for testing passing in classes directly
            config_name = config.__module__ + "." + config.__name__
    else:
        # Enables injection of a different config via Env-Variable
        if os.environ.get("SPECTER_CONFIG"):
            config = calc_module_name(os.environ.get("SPECTER_CONFIG"))
        else:
            # Default
            config = "cryptoadvance.specter.config.ProductionConfig"
        config_name = config

    app = SpecterFlask(
        __name__,
        template_folder=get_template_static_folder("templates"),
        static_folder=get_template_static_folder("static"),
    )
    app.tor_service_id = None
    app.tor_enabled = False
    app.jinja_env.autoescape = select_autoescape(default_for_string=True, default=True)
    logger.info(f"Configuration: {config}")
    app.config.from_object(config)
    logger.info(f"SPECTER_DATA_FOLDER: {app.config['SPECTER_DATA_FOLDER']}")

    # Warn if someone is running with a default SECRET_KEY on a non-localhost address.
    # This can happen if SPECTER_CONFIG isn't set and someone accidentally ships with DevelopmentConfig.
    _insecure_defaults = ("development key", "test key")
    if app.config.get("SECRET_KEY") in _insecure_defaults:
        host = app.config.get("HOST", "127.0.0.1")
        if host not in ("127.0.0.1", "localhost", "0.0.0.0"):
            logger.warning(
                "WARNING: SECRET_KEY is set to a known default value and HOST is '%s'. "
                "This is insecure for anything other than local development. "
                "Please use ProductionConfig or set a proper SECRET_KEY.",
                host,
            )
        else:
            logger.info(
                "Running with a default SECRET_KEY. Fine for local dev, not for production."
            )

    # Might be convenient to know later where it came from (see Service configuration)
    app.config["SPECTER_CONFIGURATION_CLASS_FULLNAME"] = config_name
    if not app.config.get("ENABLE_WERZEUG_REQUEST_LOGGING"):
        logging.getLogger("werkzeug").disabled = True
    app.wsgi_app = ProxyFix(
        app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1
    )
    csrf.init_app(app)
    app.csrf = csrf

    return app


def init_app(app: SpecterFlask, hwibridge=False, specter=None):
    """This code is used to initialize a Flask application.
    It sets up the app's URL prefix, runs migrations, initializes login via Flask-Login,
    sets up a user loader for the login manager, attaches the specter instance to the
    app, registers blueprints for extensions, and sets up a context processor and
    language selector for Babel integration. It also initializes a background scheduler
    and runs an after_serverpy_init_app callback.
    """

    # Configuring a prefix for the app
    if app.config["APP_URL_PREFIX"] != "":
        # https://dlukes.github.io/flask-wsgi-url-prefix.html
        app.wsgi_app = DispatcherMiddleware(
            Response("Not Found", status=404),
            {app.config["APP_URL_PREFIX"]: app.wsgi_app},
        )
    # First: Migrations
    mm = SpecterMigrator(app.config["SPECTER_DATA_FOLDER"])
    mm.execute_migrations()

    # Login via Flask-Login
    app.logger.info("Initializing LoginManager")
    app.secret_key = app.config["SECRET_KEY"]
    BitcoinRPC.default_timeout = app.config["BITCOIN_RPC_TIMEOUT"]
    LiquidRPC.default_timeout = app.config["LIQUID_RPC_TIMEOUT"]

    if specter is None:
        # the default. If not None, then it got injected for testing
        app.logger.info(
            f"Initializing Specter with data-folder {app.config['SPECTER_DATA_FOLDER']}"
        )
        specter = Specter(
            data_folder=app.config["SPECTER_DATA_FOLDER"],
            config=app.config["DEFAULT_SPECTER_CONFIG"],
            internal_bitcoind_version=app.config["INTERNAL_BITCOIND_VERSION"],
            initialize=False,
        )

    # ServiceManager will instantiate and register blueprints for extensions
    # It's an attribute to the specter but specter is not aware of it.
    # However some managers are aware of it and so we need to split
    # instantiation from initializing and in between attach the service_manager
    specter.service_manager = ExtensionManager(
        specter=specter, devstatus_threshold=app.config["SERVICES_DEVSTATUS_THRESHOLD"]
    )

    def service_manager_cleanup_on_exit(signum, frame):
        return specter.service_manager.execute_ext_callbacks(
            callbacks.cleanup_on_exit, signum, frame
        )

    specter.call_functions_at_cleanup_on_exit.append(service_manager_cleanup_on_exit)

    specter.initialize()

    # HWI
    specter.hwi = HWIBridge(app.config["SKIP_HWI_INITIALISATION_AT_STARTUP"])

    login_manager = LoginManager()
    login_manager.session_protection = app.config.get("SESSION_PROTECTION", "strong")
    login_manager.init_app(app)  # Enable Login
    login_manager.login_view = "auth_endpoint.login"  # Enable redirects if unauthorized
    app.config["SESSION_COOKIE_SAMESITE"] = "Strict"

    @login_manager.user_loader
    def user_loader(id):
        return specter.user_manager.get_user(id)

    def login(id, password: str = None):
        user = user_loader(id)
        login_user(user)

        if password:
            # Use the password while we have it to decrypt any protected
            #   user data (e.g. services).
            user.decrypt_user_secret(password)

    app.login = login
    # Attach specter instance so child views (e.g. hwi) can access it
    app.specter = specter
    # Executing callback specter_added_to_flask_app
    app.logger.info("Executing callback specter_added_to_flask_app ...")
    specter.service_manager.execute_ext_callbacks(specter_added_to_flask_app)
    if specter.config["auth"].get("method") == "none":
        app.logger.info("Login disabled")
        app.config["LOGIN_DISABLED"] = True
    else:
        app.logger.info("Login enabled")
        app.config["LOGIN_DISABLED"] = False
    app.logger.info("Initializing Controller ...")
    app.register_blueprint(hwi_server, url_prefix="/hwi")
    csrf.exempt(hwi_server)
    if not hwibridge:
        with app.app_context():
            from cryptoadvance.specter.server_endpoints import controller
            from cryptoadvance.specter.services import controller as serviceController

            # this number of view_functions needs to be updated by hand when some are added or removed.
            number_of_expected_view_functions = 105
            if app.config.get("TESTING"):
                logger.info(
                    f"We have {len(app.view_functions)} view Functions. "
                    f"There should be {number_of_expected_view_functions}."
                )
            if (
                app.config.get("TESTING")
                and len(app.view_functions) < number_of_expected_view_functions
            ):
                # Need to force a reload as otherwise the import is skipped
                # in pytest, the app is created anew for each test
                # But we shouldn't do that if not necessary as this would result in
                # --> View function mapping is overwriting an existing endpoint function
                # see archblog for more about this nasty workaround
                import importlib

                logger.info("Reloading controllers")
                importlib.reload(controller)
                importlib.reload(serviceController)
    else:

        @app.route("/", methods=["GET"])
        def index():
            return redirect(url_for("hwi_server.hwi_bridge_settings"))

    if app.config["SPECTER_API_ACTIVE"]:
        app.logger.info("Initializing REST ...")
        from cryptoadvance.specter.api import api_bp

        app.register_blueprint(api_bp)

    @app.context_processor
    def inject_tor():
        if app.config["DEBUG"]:
            return dict(tor_service_id="", tor_enabled=False)
        return dict(tor_service_id=app.tor_service_id, tor_enabled=app.tor_enabled)

    # --------------------- Babel integration ---------------------
    if getattr(sys, "frozen", False):
        app.config["BABEL_TRANSLATION_DIRECTORIES"] = os.path.join(
            sys._MEIPASS, "translations"
        )

    def get_language_code():
        # Enables Babel to auto-detect current language
        return app.get_language_code()

    babel = HTMLSafeBabel(app, locale_selector=get_language_code)

    @app.route("/set_language", methods=["POST"])
    def set_language_code():
        json_data = request.get_json()
        if (
            "language_code" in json_data
            and json_data["language_code"] in app.supported_languages
        ):
            app.set_language_code(json_data["language_code"])
            return jsonify(success=True)
        else:
            return jsonify(success=False)

    # --------------------- Babel integration ---------------------

    # Background Scheduler
    def every5seconds():
        ctx = app.app_context()
        ctx.push()
        app.specter.service_manager.execute_ext_callbacks(callbacks.every5seconds)
        ctx.pop()

    # initialize scheduler
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = APScheduler()

    scheduler.init_app(app)
    scheduler.start()
    specter.service_manager.add_required_services_to_users(specter.user_manager.users)
    logger.info("----> starting service callback_after_serverpy_init_app ")
    specter.service_manager.execute_ext_callbacks(
        after_serverpy_init_app, scheduler=scheduler
    )
    return app


def setup_logging(debug=False, tracerpc=False, tracerequests=False):
    """This code sets up logging for a Python application. It sets the logging level to DEBUG if the tracerpc
    or tracerequests flags are set, and INFO otherwise. It also sets up the formatter for the log messages,
    which can be customized with an environment variable. Finally, it adds a StreamHandler to the root
    logger and removes any existing handlers.
    """
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    if tracerpc or tracerequests:
        if tracerpc:
            debug = True  # otherwise this won't work
            logging.getLogger("cryptoadvance.specter.rpc").setLevel(logging.DEBUG)
        if tracerequests:
            # from here: https://stackoverflow.com/questions/16337511/log-all-requests-from-the-python-requests-module
            HTTPConnection.debuglevel = 1
            requests_log = logging.getLogger("requests.packages.urllib3")
            requests_log.setLevel(logging.DEBUG)
            requests_log.propagate = True
    else:
        logging.getLogger("cryptoadvance.specter.rpc").setLevel(logging.INFO)

    if debug:
        # No need for timestamps while developing (but sourcing from env-var)
        formatter = logging.Formatter(
            os.getenv(
                "SPECTER_LOGFORMAT", "[%(levelname)7s] in %(module)15s: %(message)s"
            )
        )
        logging.getLogger("cryptoadvance").setLevel(logging.DEBUG)
        # but not that chatty connectionpool
        logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
    else:
        formatter = logging.Formatter(
            # Too early to format that via the flask-config, so let's copy it from there:
            os.getenv(
                "SPECTER_LOGFORMAT",
                "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
            )
        )
        logging.getLogger("cryptoadvance").setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logging.getLogger().handlers = []
    logging.getLogger().addHandler(ch)


def setup_debug_logging():
    """Sets the cryptoadvance.* logger to debug"""
    ca_logger = logging.getLogger("cryptoadvance")
    ca_logger.setLevel(logging.DEBUG)
    logger.debug("We're now on level DEBUG on logger cryptoadvance")


def create_and_init(config="cryptoadvance.specter.config.DevelopmentConfig"):
    """This method can be used to fill the FLASK_APP-env variable like
    export FLASK_APP="src/cryptoadvance/specter/server:create_and_init()"
    See Development.md to use this for debugging. It's currently used in launch.json
    """
    setup_logging(debug=True)
    setup_debug_logging()
    app = create_app(config)
    with app.app_context():
        init_app(app)
    return app

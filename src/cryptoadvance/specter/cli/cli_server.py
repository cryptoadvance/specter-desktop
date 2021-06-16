import logging
import os
import signal
import sys
import time
from os import path
from socket import gethostname

import click
from OpenSSL import SSL, crypto
from stem.control import Controller
from urllib.parse import urlparse

from ..server import create_app, init_app
from ..util.tor import start_hidden_service, stop_hidden_services
from ..specter_error import SpecterError

logger = logging.getLogger(__name__)


@click.group()
def cli():
    pass


@cli.command()
@click.option(
    "--daemon",
    is_flag=True,
    help="Deprecated, don't use this options and expect future removal.",
)
@click.option(
    "--stop",
    is_flag=True,
    help="Deprecated, don't use this options and expect future removal.",
)
@click.option(
    "--restart",
    is_flag=True,
    help="Deprecated, don't use this options and expect future removal.",
)
@click.option(
    "--force",
    is_flag=True,
    help="Deprecated, don't use this options and expect future removal.",
)
# options below can help to run it on a remote server,
# but better use nginx
@click.option(
    "--port", help="TCP port to bind specter to"
)  # default - 25441 set to 80 for http, 443 for https
# set to 0.0.0.0 to make it available outside
@click.option(
    "--host",
    default="127.0.0.1",
    help="if you specify --host 0.0.0.0 then specter will be available in your local LAN.",
)
# for https:
@click.option(
    "--cert",
    help="--cert and --key are for specifying and using a self-signed certificate for SSL encryption.",
)
@click.option(
    "--key",
    help="--cert and --key are for specifying and using a self-signed certificate for SSL encryption.",
)
@click.option(
    "--ssl/--no-ssl",
    is_flag=True,
    default=False,
    help="By default SSL encryption will not be used. Use -ssl to create a self-signed certificate for SSL encryption. You can also specify encryption via --cert and --key.",
)
@click.option("--debug/--no-debug", default=None)
@click.option("--filelog/--no-filelog", default=True)
@click.option("--tor", is_flag=True)
@click.option(
    "--hwibridge",
    is_flag=True,
    help="Start the hwi-bridge to use your HWWs with a remote specter.",
)
@click.option(
    "--specter-data-folder",
    default=None,
    help="Use a custom specter data-folder. By default it is ~/.specter.",
)
@click.option(
    "--config",
    default=None,
    help="A class from the config.py which sets reasonable default values.",
)
def server(
    daemon,
    stop,
    restart,
    force,
    port,
    host,
    cert,
    key,
    ssl,
    debug,
    filelog,
    tor,
    hwibridge,
    specter_data_folder,
    config,
):
    # logging
    if debug:
        ca_logger = logging.getLogger("cryptoadvance")
        ca_logger.setLevel(logging.DEBUG)
        logger.debug("We're now on level DEBUG on logger cryptoadvance")

    # create an app to get Specter instance
    # and it's data folder
    if config is None:
        app = create_app()
    else:
        if "." in config:
            app = create_app(config=config)
        else:
            app = create_app(config="cryptoadvance.specter.config." + config)

    if specter_data_folder:
        app.config["SPECTER_DATA_FOLDER"] = specter_data_folder

    if port:
        app.config["PORT"] = int(port)

    # certificates
    if cert:
        logger.info("CERT:" + str(cert))
        app.config["CERT"] = cert
    if key:
        app.config["KEY"] = key

    app.app_context().push()
    init_app(app, hwibridge=hwibridge)

    if filelog:
        # again logging: Creating a logfile in SPECTER_DATA_FOLDER (which needs to exist)
        app.config["SPECTER_LOGFILE"] = os.path.join(
            app.specter.data_folder, "specter.log"
        )
        fh = logging.FileHandler(app.config["SPECTER_LOGFILE"])
        formatter = logging.Formatter(app.config["SPECTER_LOGFORMAT"])
        fh.setFormatter(formatter)
        logging.getLogger().addHandler(fh)

    # This stuff here is deprecated
    # When we remove it, we should imho keep the pid_file thing which can be very useful!
    # we will store our daemon PID here
    pid_file = path.join(app.specter.data_folder, "daemon.pid")

    toraddr_file = path.join(app.specter.data_folder, "onion.txt")
    # check if pid file exists
    if path.isfile(pid_file):
        # if we need to stop daemon
        if stop or restart:
            print("Stopping the Specter server...")
            with open(pid_file) as f:
                pid = int(f.read())
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.3)
            try:
                os.remove(pid_file)
            except OSError:
                pass
        elif daemon:
            if not force:
                print(
                    f'PID file "{pid_file}" already exists. \
                        Use --force to overwrite'
                )
                return
            else:
                os.remove(pid_file)
        if stop:
            return
    else:
        if stop or restart:
            print(f'Can\'t find PID file "{pid_file}"')
            if stop:
                return

    # watch templates folder to reload when something changes
    extra_dirs = ["templates"]
    extra_files = extra_dirs[:]
    for extra_dir in extra_dirs:
        for dirname, dirs, files in os.walk(extra_dir):
            for filename in files:
                filename = os.path.join(dirname, filename)
                if os.path.isfile(filename):
                    extra_files.append(filename)

    kwargs = {"host": host, "port": app.config["PORT"], "extra_files": extra_files}
    kwargs = configure_ssl(kwargs, app.config, ssl)

    if hwibridge:
        if kwargs.get("ssl_context"):
            logger.error(
                "Running the hwibridge is not supported via SSL. Remove --ssl, --cert, and --key options."
            )
            exit(1)
        print(
            " * Running in HWI Bridge mode.\n"
            " * You can configure access to the API "
            "at: %s://%s:%d/hwi/settings" % ("http", host, app.config["PORT"])
        )

    # debug is false by default
    def run(debug=debug):
        try:
            # if we have certificates
            if "ssl_context" in kwargs:
                tor_port = 443
            else:
                tor_port = 80
            app.port = kwargs["port"]
            app.tor_port = tor_port
            app.save_tor_address_to = toraddr_file
            if debug and (tor or os.getenv("CONNECT_TOR") == "True"):
                print(
                    " * Warning: Cannot use Tor in debug mode. \
                      Starting in production mode instead."
                )
                debug = False
            if (
                tor
                or os.getenv("CONNECT_TOR") == "True"
                or app.specter.config["tor_status"] == True
            ):
                try:
                    app.tor_enabled = True
                    start_hidden_service(app)
                    if app.specter.config["tor_status"] == False:
                        app.specter.toggle_tor_status()
                except Exception as e:
                    print(f" * Failed to start Tor hidden service: {e}")
                    print(" * Continuing process with Tor disabled")
                    app.tor_service_id = None
                    app.tor_enabled = False
            else:
                app.tor_service_id = None
                app.tor_enabled = False
            app.run(debug=debug, **kwargs)
            stop_hidden_services(app)
        finally:
            try:
                if app.specter.tor_controller is not None:
                    app.specter.tor_controller.close()
            except SpecterError as se:
                # no reason to break startup here
                logger.error("Could not initialize tor-system")

    # check if we should run a daemon or not
    if daemon or restart:
        print("Starting server in background...")
        protocol = "http"
        if "ssl_context" in kwargs:
            protocol = "https"
        print(" * Running on %s://%s:%d/" % (protocol, host, app.config["PORT"]))
        # macOS + python3.7 is buggy
        if sys.platform == "darwin" and (
            sys.version_info.major == 3 and sys.version_info.minor < 8
        ):
            raise Exception(
                " ERROR: --daemon mode is no longer \
                   supported in Python 3.7 and lower \
                   on MacOS. Upgrade to Python 3.8+. (Might not work anyway.)"
            )
        from daemonize import Daemonize

        d = Daemonize(app="specter", pid=pid_file, action=run)
        d.start()
    else:
        # if not a daemon we can use DEBUG
        if debug is None:
            debug = app.config["DEBUG"]
        run(debug=debug)


def configure_ssl(kwargs, app_config, ssl):
    """accepts kwargs and adjust them based on the config and ssl"""
    # If we should create a cert but it's not specified where, let's specify the location

    if not ssl and app_config["CERT"] is None:
        return kwargs

    if app_config["CERT"] is None:
        app_config["CERT"] = app_config["SPECTER_DATA_FOLDER"] + "/cert.pem"
    if app_config["KEY"] is None:
        app_config["KEY"] = app_config["SPECTER_DATA_FOLDER"] + "/key.pem"

    if not os.path.exists(app_config["CERT"]):
        logger.info("Creating SSL-cert " + app_config["CERT"])
        # create a key pair
        k = crypto.PKey()
        k.generate_key(crypto.TYPE_RSA, 2048)

        # create a self-signed cert
        cert = crypto.X509()
        cert.get_subject().C = app_config["SPECTER_SSL_CERT_SUBJECT_C"]
        cert.get_subject().ST = app_config["SPECTER_SSL_CERT_SUBJECT_ST"]
        cert.get_subject().L = app_config["SPECTER_SSL_CERT_SUBJECT_L"]
        cert.get_subject().O = app_config["SPECTER_SSL_CERT_SUBJECT_O"]
        cert.get_subject().OU = app_config["SPECTER_SSL_CERT_SUBJECT_OU"]
        cert.get_subject().CN = app_config["SPECTER_SSL_CERT_SUBJECT_CN"]
        cert.set_serial_number(app_config["SPECTER_SSL_CERT_SERIAL_NUMBER"])
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(10 * 365 * 24 * 60 * 60)
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(k)
        cert.sign(k, "sha1")

        open(app_config["CERT"], "wt").write(
            crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode("utf-8")
        )
        open(app_config["KEY"], "wt").write(
            crypto.dump_privatekey(crypto.FILETYPE_PEM, k).decode("utf-8")
        )

    logger.info("Configuring SSL-certificate " + app_config["CERT"])
    kwargs["ssl_context"] = (app_config["CERT"], app_config["KEY"])
    return kwargs

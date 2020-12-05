import logging
import os
import signal
import sys
import time
from os import path

import click
from stem.control import Controller

from ..server import create_app, init_app
from ..util.tor import start_hidden_service, stop_hidden_services

logger = logging.getLogger(__name__)


@click.group()
def cli():
    pass


@cli.command()
@click.option(
    "--daemon",
    is_flag=True,
    help="Deprecated, don't use that and prepare to see it removed",
)
@click.option(
    "--stop",
    is_flag=True,
    help="Deprecated, don't use that and prepare to see it removed",
)
@click.option(
    "--restart",
    is_flag=True,
    help="Deprecated, don't use that and prepare to see it removed",
)
@click.option(
    "--force",
    is_flag=True,
    help="Deprecated, don't use that and prepare to see it removed",
)
# options below can help to run it on a remote server,
# but better use nginx
@click.option(
    "--port", help="The TCP-Port to bin specter to"
)  # default - 25441 set to 80 for http, 443 for https
# set to 0.0.0.0 to make it available outside
@click.option(
    "--host",
    default="127.0.0.1",
    help="if you do --host 0.0.0.0 then specter will be available in your local lan",
)
# for https:
@click.option(
    "--cert", help="--cert and --key are for using a self-signed-cert/ssl-encryption"
)
@click.option("--key")
@click.option("--debug/--no-debug", default=None)
@click.option("--tor", is_flag=True)
@click.option(
    "--hwibridge",
    is_flag=True,
    help="Start the hwi-bridge to use your HWWs with a remote specter",
)
@click.option(
    "--specter-data-folder",
    default=None,
    help="Enables overriding the specter-data-folder. This is usually ~/.specter",
)
@click.option(
    "--config",
    default=None,
    help="A class from the config.py which sets reasonable Defaults",
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
    debug,
    tor,
    hwibridge,
    specter_data_folder,
    config,
):
    # create an app to get Specter instance
    # and it's data folder
    logger.info("Logging is hopefully configured")
    if debug:
        ca_logger = logging.getLogger("cryptoadvance")
        ca_logger.setLevel(logging.DEBUG)
        logger.debug("We're now on level DEBUG on logger cryptoadvance")
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
        key = app.config["KEY"] = key

    app.app_context().push()
    init_app(app, hwibridge=hwibridge)

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

    protocol = "http"
    kwargs = {"host": host, "port": app.config["PORT"], "extra_files": extra_files}
    if cert is not None and key is not None:
        cert = os.path.abspath(app.config["CERT"])
        key = os.path.abspath(app.config["KEY"])
        kwargs["ssl_context"] = (cert, key)
        protocol = "https"

    if hwibridge:
        print(
            " * Running HWI Bridge mode.\n"
            " * You can configure access to the API "
            "at: %s://%s:%d/hwi/settings" % (protocol, host, app.config["PORT"])
        )

    # debug is false by default
    def run(debug=debug):
        try:
            app.controller = Controller.from_port()
        except Exception:
            app.controller = None
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
            if tor or os.getenv("CONNECT_TOR") == "True":
                try:
                    app.tor_enabled = True
                    start_hidden_service(app)
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
            if app.controller is not None:
                app.controller.close()

    # check if we should run a daemon or not
    if daemon or restart:
        print("Starting server in background...")
        print(" * Hopefully running on %s://%s:%d/" % (protocol, host, port))
        # macOS + python3.7 is buggy
        if sys.platform == "darwin" and (
            sys.version_info.major == 3 and sys.version_info.minor < 8
        ):
            print(
                " * WARNING: --daemon mode might not \
                   work properly in python 3.7 and lower \
                   on MacOS. Upgrade to python 3.8+"
            )
        from daemonize import Daemonize

        d = Daemonize(app="specter", pid=pid_file, action=run)
        d.start()
    else:
        # if not a daemon we can use DEBUG
        if debug is None:
            debug = app.config["DEBUG"]
        run(debug=debug)

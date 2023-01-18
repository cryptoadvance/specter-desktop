import logging
import os
import shutil
import signal
from http.client import HTTPConnection
from pathlib import Path

import click
import psutil

logger = logging.getLogger(__name__)


class Echo:
    def __init__(self, quiet):
        self.quiet = quiet

    def echo(self, mystring, prefix=True, **kwargs):
        if self.quiet:
            pass
        else:
            if prefix:
                click.echo(f"    --> ", nl=False)
            click.echo(f"{mystring}", **kwargs)


def kill_node_process(node_impl, echo):
    did_something = False
    for proc in psutil.process_iter():
        try:
            # Get process name & pid from process object.
            if proc.name().endswith(f"{node_impl}d"):
                echo(f"Killing {node_impl}d-process with id {proc.pid} ...")
                did_something = True
                os.kill(proc.pid, signal.SIGTERM)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            echo(f"Pid {proc.pid} not owned by us. Might be a docker-process? {proc}")
    return did_something


def setup_logging(debug=False, tracerpc=False, tracerequests=False):
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
        # No need for timestamps while developing
        formatter = logging.Formatter("[%(levelname)7s] in %(module)15s: %(message)s")
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
    ca_logger = logging.getLogger("cryptoadvance")
    ca_logger.setLevel(logging.DEBUG)
    logger.debug("We're now on level DEBUG on logger cryptoadvance")


def compute_data_dir_and_set_config_obj(node_impl, data_dir, config_obj):
    if node_impl == "bitcoin":
        if data_dir:
            config_obj["BTCD_REGTEST_DATA_DIR"] = data_dir
        return config_obj["BTCD_REGTEST_DATA_DIR"]
    elif node_impl == "elements":
        if data_dir:
            config_obj["ELMD_REGTEST_DATA_DIR"] = data_dir
        return config_obj["ELMD_REGTEST_DATA_DIR"]


def purge_node_data_dir(node_impl, config_obj, echo):
    did_something = False
    if node_impl == "elements":
        data_dir = config_obj["ELMD_REGTEST_DATA_DIR"]
    elif node_impl == "bitcoin":
        data_dir = config_obj["BTCD_REGTEST_DATA_DIR"]
    else:
        raise Exception(f"unknown node_impl {node_impl}")

    if Path(data_dir).exists():
        echo(f"Purging Datadirectory {data_dir} ...")
        did_something = True
        shutil.rmtree(data_dir)
    return did_something

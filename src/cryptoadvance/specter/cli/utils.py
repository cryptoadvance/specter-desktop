import logging
import os
import shutil
import signal
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

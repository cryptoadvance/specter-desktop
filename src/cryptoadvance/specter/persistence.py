""" Provides an API abstracting writes (and reads) on anything
    happening on the ~/.specter-folder. Useful as we can then
    call the call-back-method.
"""

import os
import json
import csv
import threading
import logging
from flask import current_app as app
from .util.shell import run_shell
import shutil


logger = logging.getLogger(__name__)

fslock = threading.Lock()


def read_json_file(path):
    """read_json_file from the .specter-directory. Don't use it for
    something else"""
    with fslock:
        bkp = path + ".bkp"
        # try reading file
        try:
            with open(path, "r") as f:
                content = json.load(f)
        # if failed - try reading from the backup
        except Exception as e:
            # if no backup exists - raise
            if not os.path.isfile(bkp):
                raise e
            # try loading from backup
            with open(bkp, "r") as f:
                content = json.load(f)
            # recover from backup
            if os.path.isfile(path):
                os.remove(path)
            os.rename(bkp, path)
            logger.error(f"failed to open {path}, recovered from backup.")
        return content


def _delete_folder(path):
    """Internal method which won't trigger the callback"""
    with fslock:
        if os.path.exists(path):
            shutil.rmtree(path)


def _write_json_file(content, path, lock=None):
    """Internal method which won't trigger the callback"""
    if lock is None:
        lock = fslock
    with lock:
        # backup file
        bkp = path + ".bkp"
        # check if file exists
        if os.path.isfile(path):
            # check if backup exists
            if os.path.isfile(bkp):
                # remove backup file
                os.remove(bkp)
            # move file to backup
            os.rename(path, bkp)
        with open(path, "w") as f:
            json.dump(content, f, indent=4)
        # check if write was sucessfull
        try:
            with open(path, "r") as f:
                c = json.load(f)
        # if not - move back backup
        except:
            # remove damaged file
            if os.path.isfile(path):
                os.remove(path)
            os.rename(bkp, path)
            logger.error(f"Failed to write to file {path}")


def write_json_file(content, path, lock=None):
    _write_json_file(content, path, lock)
    storage_callback()


def delete_files(paths):
    """deletes multiple files and calls storage callback once"""
    need_callback = False
    for path in paths:
        if os.path.exists(path):
            os.remove(path)
            need_callback = True
    if need_callback:
        storage_callback()


def delete_file(path):
    delete_files([path])


def write_devices(devices_json):
    """interpret a json as a list of devices and write them in the devices subfolder inside the specter-folder"""
    for device_json in devices_json:
        _write_json_file(
            device_json,
            os.path.join(
                app.specter.device_manager.data_folder, "%s.json" % device_json["alias"]
            ),
        )
    storage_callback()


def write_wallet(wallet_json):
    """interpret a json as wallet and writes it in the wallets subfolder inside the specter-folder.
    overwrites it if existing.
    """
    fpath = os.path.join(
        app.specter.wallet_manager.working_folder, "%s.json" % wallet_json["alias"]
    )
    _write_json_file(wallet_json, fpath)
    storage_callback()


def write_device(device, fullpath):
    _write_json_file(device.json, fullpath)
    storage_callback()


def write_node(node, fullpath):
    _write_json_file(node.json, fullpath)
    storage_callback()


def delete_folder(path):
    _delete_folder(path)
    storage_callback()


def delete_folders(paths):
    for path in paths:
        _delete_folder(path)
    storage_callback()


def _write_csv(fname, objs, cls=dict):
    columns = []
    # if it's a custom class
    if hasattr(cls, "columns"):
        columns = cls.columns
    # if it's just a dict
    elif len(objs) > 0:
        columns = objs[0].keys()
    with fslock:
        with open(fname, mode="w") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            for obj in objs:
                writer.writerow(obj)


def write_csv(fname, objs, cls=dict):
    _write_csv(fname, objs, cls)
    storage_callback()


def read_csv(fname, cls=dict, *args):
    with fslock:
        with open(fname, mode="r") as csv_file:
            csv_reader = csv.DictReader(csv_file)
            return [cls(*args, **row) for row in csv_reader]


def storage_callback():
    if os.getenv("SPECTER_PERSISTENCE_CALLBACK"):
        result = run_shell(os.getenv("SPECTER_PERSISTENCE_CALLBACK").split(" "))
        if result["code"] != 0:
            logger.error("callback failed stdout: {}".format(result["out"]))
            logger.error("stderr {}".format(result["err"]))
        else:
            logger.info(
                "Successfully executed {}".format(
                    os.getenv("SPECTER_PERSISTENCE_CALLBACK")
                )
            )
            logger.debug("result: {}".format(result))

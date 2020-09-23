''' Provides an API abstracting writes (and reads) on anything
    happening on the ~/.specter-folder. Useful as we can then
    call the call-back-method.
'''

import os, json
import threading
import logging
from .util.shell import run_shell

logger = logging.getLogger(__name__)

fslock = threading.Lock()


def read_json_file(path):
    ''' read_json_file from the .specter-directory. Don't use it for 
        something else '''
    with fslock:
        with open(path, "r") as f:
            content = json.load(f)
        return content

def write_json_file(content, path, lock=None):
    _write_json_file(content,path,lock)
    storage_callback()

def delete_json_file(path):
    if os.path.exists(path):
        os.remove(path)
    storage_callback()

def _write_json_file(content, path, lock=None):
    ''' Internal method which won't trigger the callback '''
    if lock == None:
        lock = fslock
    with lock:
        with open(path, "w") as f:
            json.dump(content, f, indent=4)

def write_devices(devices):
    ''' write all the devices into the specter-folder '''
    with fslock:
        with open(
            os.path.join(
                app.specter.device_manager.data_folder,
                "%s.json" % device['alias']
            ),
            "w"
        ) as file:
            file.write(json.dumps(device, indent=4))
    storage_callback()

def write_wallet(wallet_alias, wallet): 
    with fslock:
        with open(
            os.path.join(
                app.specter.wallet_manager.working_folder,
                "%s.json" % wallet_alias
            ),
            "w"
        ) as file:
            file.write(json.dumps(wallet, indent=4))
    storage_callback()

def write_device(device, fullpath):
    with fslock:
        with open(fullpath, "w") as file:
            file.write(json.dumps(device.json, indent=4))
    storage_callback()

def delete_folder(path):
    _delete_folder(path)
    storage_callback()

def delete_folders(paths):
    for path in paths:
        _delete_folder(path)
    storage_callback()

def _delete_folder(path):
    if os.path.exists(path):
        shutil.rmtree(path)


def storage_callback():
    if os.getenv("SPECTER_PERSISTENCE_CALLBACK"):
        result = run_shell(os.getenv("SPECTER_PERSISTENCE_CALLBACK"))
        if result["code"] != 0:
            logger.error("callback failed stdout: {}".format(result["out"]))
            logger.error("stderr {}".format(result["err"]))
        else:
            logger.info("Successfully executed {}".format(os.getenv("SPECTER_PERSISTENCE_CALLBACK")))
            logger.debug("result: {}".format(result))

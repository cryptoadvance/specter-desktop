import atexit
import code
import json
import logging
import os
import shutil
import signal
import sys
import tempfile
import traceback

import pytest

from cryptoadvance.specter.config import TestConfig
from cryptoadvance.specter.managers.device_manager import DeviceManager
from cryptoadvance.specter.managers.node_manager import NodeManager
from cryptoadvance.specter.managers.user_manager import UserManager
from cryptoadvance.specter.node import Node
from cryptoadvance.specter.process_controller.bitcoind_controller import (
    BitcoindPlainController,
)
from cryptoadvance.specter.process_controller.elementsd_controller import (
    ElementsPlainController,
)
from cryptoadvance.specter.server import SpecterFlask, create_app, init_app
from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.specter_error import (
    BrokenCoreConnectionException,
    SpecterError,
    handle_exception,
)
from cryptoadvance.specter.user import User, hash_password
from cryptoadvance.specter.util.common import str2bool
from cryptoadvance.specter.util.shell import which
from cryptoadvance.specter.util.wallet_importer import WalletImporter

logger = logging.getLogger(__name__)

pytest_plugins = [
    "conftest_visibility",
    "fix_ghost_machine",
    "fix_keys_and_seeds",
    "fix_devices_and_wallets",
    "fix_testnet",
]

# This is from https://stackoverflow.com/questions/132058/showing-the-stack-trace-from-a-running-python-application
# it enables stopping a hanging test via sending the pytest-process a SIGUSR2 (12)
# kill 12 pid-of-pytest
# In the article they claim to open a debug-console which didn't work for me but at least
# you get a stacktrace in the output.
def debug(sig, frame):
    """Interrupt running process, and provide a python prompt for
    interactive debugging."""
    d = {"_frame": frame}  # Allow access to frame object.
    d.update(frame.f_globals)  # Unless shadowed by global
    d.update(frame.f_locals)

    i = code.InteractiveConsole(d)
    message = "Signal received : entering python shell.\nTraceback:\n"
    message += "".join(traceback.format_stack(frame))
    i.interact(message)


def listen():
    signal.signal(signal.SIGUSR2, debug)  # Register handler


def pytest_addoption(parser):
    """Internally called to add options to pytest
    see pytest_generate_tests(metafunc) on how to check that
    Also used to register the SIGUSR2 (12) as decribed in conftest.py
    """
    parser.addoption(
        "--bitcoind-version",
        action="store",
        default="v0.20.1",
        help="Version of bitcoind (something which works with git checkout ...)",
    )
    parser.addoption(
        "--bitcoind-log-stdout",
        action="store",
        default=False,
        help="Whether bitcoind should log to stdout (default:False)",
    )
    parser.addoption(
        "--elementsd-version",
        action="store",
        default="master",
        help="Version of elementsd (something which works with git checkout ...)",
    )
    listen()


def pytest_generate_tests(metafunc):
    # ToDo: use custom compiled version of bitcoind
    # E.g. test again bitcoind version [currentRelease] + master-branch
    if "docker" in metafunc.fixturenames:
        if metafunc.config.getoption("docker"):
            # That's a list because we could do both (see above) but currently that doesn't make sense in that context
            metafunc.parametrize("docker", [True], scope="session")
        else:
            metafunc.parametrize("docker", [False], scope="session")


def instantiate_bitcoind_controller(
    request, rpcport=18543, extra_args=[]
) -> BitcoindPlainController:
    # logging.getLogger().setLevel(logging.DEBUG)
    requested_version = request.config.getoption("--bitcoind-version")
    log_stdout = str2bool(request.config.getoption("--bitcoind-log-stdout"))
    if os.path.isfile("tests/bitcoin/src/bitcoind"):
        bitcoind_controller = BitcoindPlainController(
            bitcoind_path="tests/bitcoin/src/bitcoind", rpcport=rpcport
        )  # always prefer the self-compiled bitcoind if existing
    elif os.path.isfile("tests/bitcoin/bin/bitcoind"):
        bitcoind_controller = BitcoindPlainController(
            bitcoind_path="tests/bitcoin/bin/bitcoind", rpcport=rpcport
        )  # next take the self-installed binary if existing
    else:
        bitcoind_controller = BitcoindPlainController(
            rpcport=rpcport
        )  # Alternatively take the one on the path for now
    bitcoind_controller.start_bitcoind(
        cleanup_at_exit=True,
        cleanup_hard=True,
        extra_args=extra_args,
        log_stdout=log_stdout,
    )
    assert not bitcoind_controller.datadir is None
    running_version = bitcoind_controller.version()
    requested_version = request.config.getoption("--bitcoind-version")
    assert running_version == requested_version, (
        "Please make sure that the Bitcoind-version (%s) matches with the version in pyproject.toml (%s)"
        % (running_version, requested_version)
    )
    return bitcoind_controller


def instantiate_elementsd_controller(request, rpcport=18643, extra_args=[]):
    if os.path.isfile("tests/elements/src/elementsd"):
        elementsd_controller = ElementsPlainController(
            elementsd_path="tests/elements/src/elementsd", rpcport=rpcport
        )  # always prefer the self-compiled bitcoind if existing
    elif os.path.isfile("tests/elements/bin/elementsd"):
        elementsd_controller = ElementsPlainController(
            elementsd_path="tests/elements/bin/elementsd", rpcport=rpcport
        )  # next take the self-installed binary if existing
    else:
        elementsd_controller = ElementsPlainController(
            rpcport=rpcport
        )  # Alternatively take the one on the path for now
    elementsd_controller.start_elementsd(
        cleanup_at_exit=True, cleanup_hard=True, extra_args=extra_args
    )
    assert not elementsd_controller.datadir is None
    running_version = elementsd_controller.version()
    requested_version = request.config.getoption("--elementsd-version")
    assert running_version == requested_version, (
        "Please make sure that the elementsd-version (%s) matches with the version in pyproject.toml (%s)"
        % (running_version, requested_version)
    )
    return elementsd_controller


# Below this point are fixtures. Fixtures have a scope. Check about scopes here:
# https://docs.pytest.org/en/6.2.x/fixture.html#scope-sharing-fixtures-across-classes-modules-packages-or-session
# possible values: function, class, module, package or session.
# The nodes are of scope session. All else is the default (function)


@pytest.fixture(scope="session")
def bitcoind_path():
    if os.path.isfile("tests/bitcoin/src/bitcoind"):
        return "tests/bitcoin/src/bitcoind"
    elif os.path.isfile("tests/bitcoin/bin/bitcoind"):
        return "tests/bitcoin/bin/bitcoind"
    else:
        return which("bitcoind")


@pytest.fixture(scope="session")
def bitcoin_regtest(request) -> BitcoindPlainController:
    bitcoind_regtest = instantiate_bitcoind_controller(request, extra_args=None)
    try:
        assert bitcoind_regtest.get_rpc().test_connection()
        assert not bitcoind_regtest.datadir is None
        assert bitcoind_regtest.datadir is not ""
        yield bitcoind_regtest
    finally:
        bitcoind_regtest.stop_bitcoind()


@pytest.fixture(scope="session")
def bitcoin_regtest2(request) -> BitcoindPlainController:
    """If a test needs two nodes ..."""
    bitcoind_regtest = instantiate_bitcoind_controller(
        request, rpcport=18544, extra_args=None
    )
    try:
        assert bitcoind_regtest.get_rpc().test_connection()
        assert not bitcoind_regtest.datadir is None
        yield bitcoind_regtest
    finally:
        bitcoind_regtest.stop_bitcoind()


@pytest.fixture
def node(empty_data_folder, bitcoin_regtest):
    nodes_folder = empty_data_folder + "/nodes"
    if not os.path.isdir(nodes_folder):
        os.makedirs(nodes_folder)
    nm = NodeManager(data_folder=nodes_folder)
    node: Node = nm.add_external_node(
        "BTC",
        "Standard node",
        False,
        bitcoin_regtest.datadir,
        bitcoin_regtest.rpcconn.rpcuser,
        bitcoin_regtest.rpcconn.rpcpassword,
        bitcoin_regtest.rpcconn.rpcport,
        bitcoin_regtest.rpcconn._ipaddress,
        "http",
    )
    assert node.rpc.test_connection()
    return node


@pytest.fixture
def node_with_different_port(empty_data_folder, bitcoin_regtest):
    nodes_folder = empty_data_folder + "/nodes"
    if not os.path.isdir(nodes_folder):
        os.makedirs(nodes_folder)
    nm = NodeManager(data_folder=nodes_folder)
    node = nm.add_external_node(
        "BTC",
        "Node with a different port",
        False,
        "",
        bitcoin_regtest.rpcconn.rpcuser,
        bitcoin_regtest.rpcconn.rpcpassword,
        18333,
        bitcoin_regtest.rpcconn._ipaddress,
        "http",
    )
    return node


@pytest.fixture
def node_with_empty_datadir(empty_data_folder, bitcoin_regtest):
    nodes_folder = empty_data_folder + "/nodes"
    if not os.path.isdir(nodes_folder):
        os.makedirs(nodes_folder)
    node = Node.from_json(
        {
            "autodetect": False,
            "datadir": "",
            "user": bitcoin_regtest.rpcconn.rpcuser,
            "password": bitcoin_regtest.rpcconn.rpcpassword,
            "port": bitcoin_regtest.rpcconn.rpcport,
            "host": bitcoin_regtest.rpcconn.ipaddress,
            "protocol": "http",
        },
        manager=NodeManager(data_folder=nodes_folder),
        default_fullpath=os.path.join(nodes_folder, "node_with_empty_datadir.json"),
    )
    return node


@pytest.fixture(scope="session")
def elements_elreg(request):
    elements_elreg = instantiate_elementsd_controller(request, extra_args=None)
    try:
        yield elements_elreg
        assert not elements_elreg.datadir is None
    finally:
        elements_elreg.stop_elementsd()


@pytest.fixture
def empty_data_folder():
    # Make sure that this folder never ever gets a reasonable non-testing use-case
    with tempfile.TemporaryDirectory(
        prefix="specter_home_tmp_", ignore_cleanup_errors=False
    ) as data_folder:
        yield data_folder


@pytest.fixture
def devices_filled_data_folder(empty_data_folder):
    devices_folder = empty_data_folder + "/devices"
    if not os.path.isdir(devices_folder):
        os.makedirs(devices_folder)

    shutil.copy2(
        "./tests/misc_testdata/trezor_device.json",
        empty_data_folder + "/devices/trezor.json",
    )
    shutil.copy2(
        "./tests/misc_testdata/specter_device.json",
        empty_data_folder + "/devices/specter.json",
    )
    return empty_data_folder  # no longer empty, though


@pytest.fixture
def wallets_filled_data_folder(devices_filled_data_folder):
    simple_json = """
{
    "alias": "simple",
    "fullpath": "/home/kim/.specter/wallets/regtest/simple.json",
    "name": "Simple",
    "address_index": 0,
    "keypool": 5,
    "address": "bcrt1qcatuhg0gll3h7py4cmn53rjjn9xlsqfwj3zcej",
    "change_index": 0,
    "change_address": "bcrt1qt28v03278lmmxllys89acddp2p5y4zds94944n",
    "change_keypool": 5,
    "type": "simple",
    "description": "Single (Segwit)",
    "keys": [{
        "derivation": "m/84h/1h/0h",
        "original": "vpub5Y35MNUT8sUR2SnRCU9A9S6z1JDACMTuNnM8WHXvuS7hCwuVuoRAWJGpi66Yo8evGPiecN26oLqx19xf57mqVQjiYb9hbb4QzbNmFfsS9ko",
        "fingerprint": "1ef4e492",
        "type": "wpkh",
        "xpub": "tpubDC5EUwdy9WWpzqMWKNhVmXdMgMbi4ywxkdysRdNr1MdM4SCfVLbNtsFvzY6WKSuzsaVAitj6FmP6TugPuNT6yKZDLsHrSwMd816TnqX7kuc"
    }],
    "recv_descriptor": "wpkh([1ef4e492/84h/1h/0h]tpubDC5EUwdy9WWpzqMWKNhVmXdMgMbi4ywxkdysRdNr1MdM4SCfVLbNtsFvzY6WKSuzsaVAitj6FmP6TugPuNT6yKZDLsHrSwMd816TnqX7kuc/0/*)#xp8lv5nr",
    "change_descriptor": "wpkh([1ef4e492/84h/1h/0h]tpubDC5EUwdy9WWpzqMWKNhVmXdMgMbi4ywxkdysRdNr1MdM4SCfVLbNtsFvzY6WKSuzsaVAitj6FmP6TugPuNT6yKZDLsHrSwMd816TnqX7kuc/1/*)#h4z73prm",
    "device": "Trezor",
    "device_type": "trezor",
    "address_type": "bech32"
}
"""
    another_wallet_json = """
{
    "name": "sdsd",
    "alias": "sdsd",
    "description": "Single (Segwit)",
    "address_type": "bech32",
    "address": "bcrt1q4h86vfanswhsle63hw2muv9h5a45cg2878uez5",
    "address_index": 0,
    "change_address": "bcrt1qxsj28ddr95xvp7xjyzkkfq6qknrn4kap30zkut",
    "change_index": 0,
    "keypool": 60,
    "change_keypool": 20,
    "recv_descriptor": "wpkh([41490ec7/84h/1h/0h]tpubDCTPz7KwyetfhQNMSWiK34pPR2zSTsTybrMPgRVAzouNLqtgsv51o81KjccmTbjkWJ8mVhRJM1LxZD6AfRH2635tHpHeCAKW446iwADNv7C/0/*)#rn833s5g",
    "change_descriptor": "wpkh([41490ec7/84h/1h/0h]tpubDCTPz7KwyetfhQNMSWiK34pPR2zSTsTybrMPgRVAzouNLqtgsv51o81KjccmTbjkWJ8mVhRJM1LxZD6AfRH2635tHpHeCAKW446iwADNv7C/1/*)#j8zsv9ys",
    "keys": [
        {
            "original": "vpub5YRErYARy1rFj1oGKc9yQyJ1jybtbEyvDziem5eFttPiVMbXJNtoQZ2DTAcowHUfu7NFPAiJtaop6TNRqAbkc8GPVY9VLp2HveP2PygjuYh",
            "fingerprint": "41490ec7",
            "derivation": "m/84h/1h/0h",
            "type": "wpkh",
            "purpose": "#0 Single Sig (Segwit)",
            "xpub": "tpubDCTPz7KwyetfhQNMSWiK34pPR2zSTsTybrMPgRVAzouNLqtgsv51o81KjccmTbjkWJ8mVhRJM1LxZD6AfRH2635tHpHeCAKW446iwADNv7C"
        }
    ],
    "devices": [
        "dsds"
    ],
    "sigs_required": 1,
    "blockheight": 0,
    "pending_psbts": {},
    "frozen_utxo": [],
    "last_block": "187e2db380eb6d901efd87188f00c7074506c9c3813b8ecec7300ecc4e55eb46"
}
"""

    os.makedirs(os.path.join(devices_filled_data_folder, "wallets", "regtest"))
    with open(
        os.path.join(devices_filled_data_folder, "wallets", "regtest", "simple.json"),
        "w",
    ) as json_file:
        json_file.write(simple_json)
    os.makedirs(os.path.join(devices_filled_data_folder, "wallets_someuser", "regtest"))
    with open(
        os.path.join(
            devices_filled_data_folder, "wallets_someuser", "regtest", "simple.json"
        ),
        "w",
    ) as json_file:
        json_file.write(another_wallet_json)
    return devices_filled_data_folder  # and with wallets obviously


@pytest.fixture
def device_manager(devices_filled_data_folder):
    return DeviceManager(os.path.join(devices_filled_data_folder, "devices"))


# @pytest.fixture
# def user_manager(empty_data_folder) -> UserManager:
#     """A UserManager having users alice, bob and eve"""
#     specter = Specter(data_folder=empty_data_folder)
#     user_manager = UserManager(specter=specter)
#     config = {}
#     user_manager.get_user("admin").decrypt_user_secret("admin")
#     user_manager.create_user(
#         user_id="alice",
#         username="alice",
#         plaintext_password="plain_pass_alice",
#         config=config,
#     )
#     user_manager.create_user(
#         user_id="bob",
#         username="bob",
#         plaintext_password="plain_pass_bob",
#         config=config,
#     )
#     user_manager.create_user(
#         user_id="eve",
#         username="eve",
#         plaintext_password="plain_pass_eve",
#         config=config,
#     )
#     return user_manager


@pytest.fixture
def specter_regtest_configured(bitcoin_regtest, devices_filled_data_folder, node):
    assert bitcoin_regtest.get_rpc().test_connection()
    config = {
        "rpc": {
            "autodetect": False,
            "datadir": bitcoin_regtest.datadir,
            "user": bitcoin_regtest.rpcconn.rpcuser,
            "password": bitcoin_regtest.rpcconn.rpcpassword,
            "port": bitcoin_regtest.rpcconn.rpcport,
            "host": bitcoin_regtest.rpcconn.ipaddress,
            "protocol": "http",
        },
        "auth": {
            "method": "rpcpasswordaspin",
        },
        "testing": {
            "allow_threading_for_testing": False,
        },
    }
    specter: Specter = Specter(
        data_folder=devices_filled_data_folder, config=config, checker_threads=False
    )
    assert specter.active_node_alias == "bitcoin_core"
    assert specter.node_manager.active_node.alias == "bitcoin_core"
    assert specter.chain == "regtest"
    # Create a User
    someuser = specter.user_manager.add_user(
        User.from_json(
            user_dict={
                "id": "someuser",
                "username": "someuser",
                "password": hash_password("somepassword"),
                "config": {},
                "is_admin": False,
                "services": None,
            },
            specter=specter,
        )
    )
    specter.user_manager.save()
    specter.check()

    assert not specter.wallet_manager.working_folder is None
    try:
        yield specter
    finally:
        # End all threads
        # Deleting all Wallets (this will also purge them on core)
        for user in specter.user_manager.users:
            for wallet in list(user.wallet_manager.wallets.values()):
                user.wallet_manager.delete_wallet(wallet, node)


@pytest.fixture
def specter_regtest_configured_with_threading(
    bitcoin_regtest, devices_filled_data_folder, node
):
    assert bitcoin_regtest.get_rpc().test_connection()
    config = {
        "rpc": {
            "autodetect": False,
            "datadir": bitcoin_regtest.datadir,
            "user": bitcoin_regtest.rpcconn.rpcuser,
            "password": bitcoin_regtest.rpcconn.rpcpassword,
            "port": bitcoin_regtest.rpcconn.rpcport,
            "host": bitcoin_regtest.rpcconn.ipaddress,
            "protocol": "http",
        },
        "auth": {
            "method": "rpcpasswordaspin",
        },
        "testing": {
            "allow_threading_for_testing": True,
        },
    }
    specter = Specter(data_folder=devices_filled_data_folder, config=config)
    assert specter.chain == "regtest"
    # Create a User
    someuser = specter.user_manager.add_user(
        User.from_json(
            user_dict={
                "id": "someuser",
                "username": "someuser",
                "password": hash_password("somepassword"),
                "config": {},
                "is_admin": False,
                "services": None,
            },
            specter=specter,
        )
    )
    specter.user_manager.save()
    specter.check()

    assert not specter.wallet_manager.working_folder is None
    try:
        yield specter
    finally:
        # Deleting all Wallets (this will also purge them on core)
        for user in specter.user_manager.users:
            for wallet in list(user.wallet_manager.wallets.values()):
                user.wallet_manager.delete_wallet(wallet, node)


def specter_app_with_config(config={}, specter=None):
    """helper-function to create SpecterFlasks"""
    if isinstance(config, dict):
        tempClass = type("tempClass", (TestConfig,), {})
        for key, value in config.items():
            setattr(tempClass, key, value)
        # service_manager will expect the class to be defined as a direct property of the module:
        if hasattr(sys.modules[__name__], "tempClass"):
            delattr(sys.modules[__name__], "tempClass")
        assert not hasattr(sys.modules[__name__], "tempClass")
        setattr(sys.modules[__name__], "tempClass", tempClass)
        assert hasattr(sys.modules[__name__], "tempClass")
        assert getattr(sys.modules[__name__], "tempClass") == tempClass
        config = tempClass
    app = create_app(config=config)
    app.app_context().push()
    app.config["TESTING"] = True
    app.testing = True
    app.tor_service_id = None
    app.tor_enabled = False
    init_app(app, specter=specter)
    return app


@pytest.fixture
def app(specter_regtest_configured) -> SpecterFlask:
    """the Flask-App, but uninitialized"""
    return specter_app_with_config(
        config="cryptoadvance.specter.config.TestConfig",
        specter=specter_regtest_configured,
    )


@pytest.fixture
def app_no_node(empty_data_folder) -> SpecterFlask:
    specter = Specter(data_folder=empty_data_folder, checker_threads=False)
    app = create_app(config="cryptoadvance.specter.config.TestConfig")
    app.app_context().push()
    app.config["TESTING"] = True
    app.testing = True
    app.tor_service_id = None
    app.tor_enabled = False
    init_app(app, specter=specter)
    return app


@pytest.fixture
def client(app):
    """a test_client from an initialized Flask-App"""
    return app.test_client()

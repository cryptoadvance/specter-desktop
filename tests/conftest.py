import atexit
import code
import json
import logging
import os
import signal
import sys
import tempfile
import traceback

import pytest
from cryptoadvance.specter.config import TestConfig
from cryptoadvance.specter.node import Node
from cryptoadvance.specter.managers.device_manager import DeviceManager
from cryptoadvance.specter.managers.node_manager import NodeManager
from cryptoadvance.specter.managers.user_manager import UserManager
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
        "Please make sure that the Bitcoind-version (%s) matches with the version in pytest.ini (%s)"
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
        "Please make sure that the elementsd-version (%s) matches with the version in pytest.ini (%s)"
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
    with open(empty_data_folder + "/devices/trezor.json", "w") as text_file:
        text_file.write(
            """
{
    "name": "Trezor",
    "alias": "mytrezor",
    "type": "trezor",
    "keys": [
        {
            "original": "upub5EKoQv21nQNkhdt4yuLyRnWitA3EGhW1ru1Y8VTG8gdys2JZhqiYkhn4LHp2heHnH41kz95bXPvrYVRuFUrdUMik6YdjFV4uL4EubnesttQ",
            "fingerprint": "1ef4e492",
            "derivation": "m/49h/1h/0h",
            "type": "sh-wpkh",
            "purpose": "#0 Single Sig (Nested)",
            "xpub": "tpubDDCDr9rSwixeXKeGwAgwFy8bjBaE5wya9sAVqEC4ccXWmcQxY34KmLRJdwmaDsCnHsu5r9P9SUpYtXmCoRwukWDqmAUJgkBbjC2FXUzicn6"
        },
        {
            "original": "vpub5Y35MNUT8sUR2SnRCU9A9S6z1JDACMTuNnM8WHXvuS7hCwuVuoRAWJGpi66Yo8evGPiecN26oLqx19xf57mqVQjiYb9hbb4QzbNmFfsS9ko",
            "fingerprint": "1ef4e492",
            "derivation": "m/84h/1h/0h",
            "type": "wpkh",
            "purpose": "#0 Single Sig (Segwit)",
            "xpub": "tpubDC5EUwdy9WWpzqMWKNhVmXdMgMbi4ywxkdysRdNr1MdM4SCfVLbNtsFvzY6WKSuzsaVAitj6FmP6TugPuNT6yKZDLsHrSwMd816TnqX7kuc"
        },
        {
            "original": "Upub5Tk9tZtdzVaTGWtygRTKDDmaN5vfB59pn2L5MQyH6BkVpg2Y5J95rtpQndjmXNs3LNFiy8zxpHCTtvxxeePjgipF7moTHQZhe3E5uPzDXh8",
            "fingerprint": "1ef4e492",
            "derivation": "m/48h/1h/0h/1h",
            "type": "sh-wsh",
            "purpose": "#0 Multisig Sig (Nested)",
            "xpub": "tpubDFiVCZzdarbyfdVoh2LJDL3eVKRPmxwnkiqN8tSYCLod75a2966anQbjHajqVAZ97j54xZJPr9hf7ogVuNL4pPCfwvXdKGDQ9SjZF7vXQu1"
        },
        {
            "original": "Vpub5naRCEZZ9B7wCKLWuqoNdg6ddWEx8ruztUygXFZDJtW5LRMqUP5HV2TsNw1nc74Ba3QPDSH7qzauZ8LdfNmnmofpfmztCGPgP7vaaYSmpgN",
            "fingerprint": "1ef4e492",
            "derivation": "m/48h/1h/0h/2h",
            "type": "wsh",
            "purpose": "#0 Multisig Sig (Segwit)",
            "xpub": "tpubDFiVCZzdarbyk8kE65tjRhHCambEo8iTx4xkXL8b33BKZj66HWsDnUb3rg4GZz6Mwm6vTNyzRCjYtiScCQJ77ENedb2deDDtcoNQXiUouJQ"
        },
        {
            "original": "upub5EKoQv21nQNkkbeX7RLSUgcjnR6nTWFudhmGo5Nxq48FqkKxgPBkWiAwKazG3cd1KjENnTbeGJtNB7iqyuH4QXpxFnVvsRtbGkN2Fg9wStD",
            "fingerprint": "1ef4e492",
            "derivation": "m/49h/1h/1h",
            "type": "sh-wpkh",
            "purpose": "#1 Single Sig (Nested)",
            "xpub": "tpubDDCDr9rSwixeaHQj4ggQJsEcdSdnGkjTvfvEVp7mJz1nkLSMWaXXXLpBdEwoZqY1LZ7heTuCBPn4XA49XrNLggL3vQLWJh1Hft9NBQDrZ29"
        },
        {
            "original": "vpub5Y35MNUT8sUR6SVwH1nkeiUwWky58XopeJaFWLwJfQj2GgcGFbwmkmhp3yBMEVTqw2xfvzpvMqSUzCXiGZdxAiWyvmxyyrErPBwPoKSJzus",
            "fingerprint": "1ef4e492",
            "derivation": "m/84h/1h/1h",
            "type": "wpkh",
            "purpose": "#1 Single Sig (Segwit)",
            "xpub": "tpubDC5EUwdy9WWq4q52PvM6Gp1KBpMd1AHt2ACzRgnDmLEg8AuRq97z9LgvLRBJkoivYDjC3XXupFydSxFT6pKDedLUj478qCY4Wbf6LZHaEuo"
        },
        {
            "original": "Upub5SNDKzLBXW3QBrbxK14LDuVtxxR2MWYxChNjShS338xKtx1tgwp1tZoM5Prts4J2DXpPKATS1vfntAHrorEXZA7VFBCaUNhemfWYejJRPHg",
            "fingerprint": "1ef4e492",
            "derivation": "m/48h/1h/1h/1h",
            "type": "sh-wsh",
            "purpose": "#1 Multisig Sig (Nested)",
            "xpub": "tpubDELYdzSB7s4vayCnKbwKE1my6BukxQLvBPt2EAuJ9J1TBMZNkjmWp5afaLrxpqz7ztdjJaks3oAz731Q4aArgpVv5KvkWEMMH521zaj118Z"
        },
        {
            "original": "Vpub5mCUdf16gBat7LhtqCQne7zV3en2XV2nodPGR85jhHqv9E4A7UXNnZ9UsA5x3H2fxhc38t5gXcp1XvqGp8ASa3ErgXhyFKNAt1cSMdWGXNN",
            "fingerprint": "1ef4e492",
            "derivation": "m/48h/1h/1h/2h",
            "type": "wsh",
            "purpose": "#1 Multisig Sig (Segwit)",
            "xpub": "tpubDELYdzSB7s4vfA7c1SW9S9B3zv8KBkqFsDNLRCf7RSXANXnQvcKK61GfLu8S1A4rLRJaNpnZ6pxesWwFM9gkuTwgeLjihGCP7h4GJuCxsd3"
        },
        {
            "original": "upub5EKoQv21nQNknik1KU1syMoEgo8NwkDkYeX6hYSTexRhSdCXqNHHHKsd9W1o8qvqRgqfBP9KmuWBxuMWvmCMqMSicMBqwCJGGa5TVau3eD1",
            "fingerprint": "1ef4e492",
            "derivation": "m/49h/1h/2h",
            "type": "sh-wpkh",
            "purpose": "#2 Single Sig (Nested)",
            "xpub": "tpubDDCDr9rSwixecQWDGjMqoYR7XpfNkzhJqcg4QHBG8tKEMDJvfZd4HxWsT9yLf4qqSWiz3PSsgzPtJwgpUiHe7VwpGy2RNTQxfhroRPqfBfM"
        },
        {
            "original": "vpub5Y35MNUT8sUR85w9G2bVdZQrHWXLdxPcsi75fgnBWkJNATPfgbv4Qpabv59fMTG5cVdePeveifFk5TPePFdU7jvPm1qb9fVYcxXKXSvUtgz",
            "fingerprint": "1ef4e492",
            "derivation": "m/84h/1h/2h",
            "type": "wpkh",
            "purpose": "#2 Single Sig (Segwit)",
            "xpub": "tpubDC5EUwdy9WWq6UWENw9qFewDxZutWasgFZjpb2d6cfp21wgqG96GoPZiCX9csmXADgQAWBdeB5ntYD7PDWJjbejtZHyk11nkkNF24i7RnLV"
        },
        {
            "original": "Upub5TVK2qPsm6eMaSm9JpaDCqGACPHtXMmn6reTthgdvpqnV7qcyHD3awVpEawcMxRKDbEyvMLr1pKNWFAQYBhzfwzrAo8BpMefcymgMsYvdw4",
            "fingerprint": "1ef4e492",
            "derivation": "m/48h/1h/2h/1h",
            "type": "sh-wsh",
            "purpose": "#2 Multisig Sig (Nested)",
            "xpub": "tpubDFTeLqVsMTfsyZMyKRTCCwYEKcnd8FZk5Z9kgB9u2ytumXP735AYWTH8jXwgKk7Qzx4KumeH3gpZj7swnueKocPGzwrMrDJN8PH9hh7AnfJ"
        },
        {
            "original": "Vpub5nKaLW4nunBqSzRVKf4oTaGySWh8kTJUd3wQHvVMnNp4ksukeC7spEmCyKRfAEHz31UPAkBGQwrEwS5iFpQbuNB4EuigfoTLTSwYmXXP2JK",
            "fingerprint": "1ef4e492",
            "derivation": "m/48h/1h/2h/2h",
            "type": "wsh",
            "purpose": "#2 Multisig Sig (Segwit)",
            "xpub": "tpubDFTeLqVsMTfszoqCVuAAFbTYPn3RQj6wgdvUJ14jWXVJzBe1TKup7gtPT4U987LAQjAvQgt8z9ztH2BgnqvvEnstCikS7kHYh8PNimvL3mt"
        },
        {
            "original": "upub5EKoQv21nQNkquuCusEL8ofnQaM4V8rsdzPuWe48FD4rRWvmF61hEqVMwwNje2zxpma7ju39zT1ub1hogbGaKdAvmMfPJtdqCSR5FovbUSF",
            "fingerprint": "1ef4e492",
            "derivation": "m/49h/1h/3h",
            "type": "sh-wpkh",
            "purpose": "#3 Single Sig (Nested)",
            "xpub": "tpubDDCDr9rSwixefbfQs8aHxzHfFbt4JPLRvxYsDNnvj8xPL73A5HMUFU8cFbLHAFuxqbTSbuLhuXubw437EYMrbmg2RyVxk9kXbaCRBYbHftq"
        },
        {
            "original": "vpub5Y35MNUT8sURA6hs4HJw67NHTFmMsmjDSu9pQS3abpJDrkUdSpXn7n5WEVHvU2uuJWAKHSkdpDYKuFBvhQAJ2xtezVurh2WfBMsP8HorJxH",
            "fingerprint": "1ef4e492",
            "derivation": "m/84h/1h/3h",
            "type": "wpkh",
            "purpose": "#3 Single Sig (Segwit)",
            "xpub": "tpubDC5EUwdy9WWq8VGxBBsGiCtf8K9ukQDGpknZKmtVhjosiEmo2MhzWM4cWwHszMAyugvqPyTdGe5UMzufXeqZWsi9nn41YNosJmb5fYoCqFy"
        },
        {
            "original": "Upub5TYty5hhC1kpHss1TPBrhzsP7Jy2UScv6VF8HeEN1jbvVhryoPsrN9sBGxWjcvJp4TZLdkaqKmEvLqFP2CVtnSFw4Vv4HcG1pcp66PCAxnr",
            "fingerprint": "1ef4e492",
            "derivation": "m/48h/1h/3h/1h",
            "type": "sh-wsh",
            "purpose": "#3 Multisig Sig (Nested)",
            "xpub": "tpubDFXEH5ognNnLgzTqTz4qi79TEYTm5LQt5BkR57hd7tf3n7QTsBqMHfeVmuWoahzuqpNgdAtGMdk7ZhxvGvSDv6eMteeEKTuiL2KZS7oDNBc"
        },
        {
            "original": "Vpub5nPAGkNcLhJJCHZhGRt47wH5mBab9m5PfJmUjSazw1XAkbax3vG9RCJQVMei2Z84PgirRvTUHU93uUXynBUXwiiPVT4VwG45Xas6KWDPh5T",
            "fingerprint": "1ef4e492",
            "derivation": "m/48h/1h/3h/2h",
            "type": "wsh",
            "purpose": "#3 Multisig Sig (Segwit)",
            "xpub": "tpubDFXEH5ognNnLk6yQSfyQuxTeiSvsp2sritkYjXANfACQyuKCs445ieRay6hBzSAEmQRPfsALrgHhF4dxKCzrH9RDTG6FPCtHmGJvGi6sSC8"
        },
        {
            "original": "upub5EKoQv21nQNktcVEn7ormrgocRuFrKvU6wum7ZRfXcTKYtfUfG1RXihAgq4cWyTVM4smEV5VTejiCXot2akjMDr6sYCghMnqUSVuNctuCbm",
            "fingerprint": "1ef4e492",
            "derivation": "m/49h/1h/4h",
            "type": "sh-wpkh",
            "purpose": "#4 Single Sig (Nested)",
            "xpub": "tpubDDCDr9rSwixeiJFSjP9pc3JgTTSFfaQ2Pv4ipJAU1YLrTUmsVTMCYMLQzV2A3CNVMtm66VP3NjdQYa9BaXr1dNMCYA3G8cuXsaHFJMZNVDP"
        },
        {
            "original": "vpub5Y35MNUT8sUREDYApTNH7Y188zckaDj6NHaK8tkgRFLsjF2a8cQRXrSzgvJbMoEgHgqZm8259DGsHUXmUA8P3FKEFkjNeMh7aMaivei27JR",
            "fingerprint": "1ef4e492",
            "derivation": "m/84h/1h/4h",
            "type": "wpkh",
            "purpose": "#4 Single Sig (Segwit)",
            "xpub": "tpubDC5EUwdy9WWqCc7FwMvcjdXVp41JSrD9k9D44EbbXArXajKji9advRS6yNJYt7Vktsc5sej4bdp1kEFWJQoeXA8j42sXVhzKhmJRTmvjiZL"
        },
        {
            "original": "Upub5TNPzsZrx1ZhKLgEqViJqi6cWUrUyQdPpCwFQ1fbBqtVBGC6CwCscoqnH34TEGGbWnEL4C2eJDPnsqcM2sGnPZXuyH7Dy511H3qnCVK7P5f",
            "fingerprint": "1ef4e492",
            "derivation": "m/48h/1h/4h/1h",
            "type": "sh-wsh",
            "purpose": "#4 Multisig Sig (Nested)",
            "xpub": "tpubDFLjJsfrYNbDiTH4r6bHqpNgdiMDaJRMnuSYBV8rHzwcTfjaGjANYKd6mz4XC3xhJ93g3cL5L5tz6iKtHbD7XDvLoRqPzvehnTMFYEJv8rh"
        },
        {
            "original": "Vpub5nCfJYEn6h7BDYF3ZiuhYa6RgEb6FnVb2ewjDpiYEWKyQVuuHuise1Ygbo1r5EggzF1zfyDSCmywMieJKCR3q1Ergim9UQSUZEWrpGkeBvk",
            "fingerprint": "1ef4e492",
            "derivation": "m/48h/1h/4h/2h",
            "type": "wsh",
            "purpose": "#4 Multisig Sig (Segwit)",
            "xpub": "tpubDFLjJsfrYNbDmMekjy14LbGzdVwNv4J46EvoDuHuxf1DdoeA73WowTfs5Y4L37isMxiXuuvJmz8ahJkGrDwNARwgeXntvMGgnuxgmXxNsnU"
        }
    ]
}
"""
        )
    with open(empty_data_folder + "/devices/specter.json", "w") as text_file:
        text_file.write(
            """
{
    "name": "Specter",
    "type": "specter",
    "keys": [
        {
            "derivation": "m/48h/1h/0h/2h",
            "original": "Vpub5n9kKePTPPGtw3RddeJWJe29epEyBBcoHbbPi5HhpoG2kTVsSCUzsad33RJUt3LktEUUPPofcZczuudnwR7ZgkAkT6N2K2Z7wdyjYrVAkXM",
            "fingerprint": "08686ac6",
            "type": "wsh",
            "xpub": "tpubDFHpKypXq4kwUrqLotPs6fCic5bFqTRGMBaTi9s5YwwGymE8FLGwB2kDXALxqvNwFxB1dLWYBmmeFVjmUSdt2AsaQuPmkyPLBKRZW8BGCiL"
        },
        {
            "derivation": "m/84h/1h/0h",
            "original": "vpub5ZSem3mLXiSJzgDX6pJb2N9L6sJ8m6ejaksLPLSuB53LBzCi2mMsBg19eEUSDkHtyYp75GATjLgt5p3S43WjaVCXAWU9q9H5GhkwJBrMiAb",
            "fingerprint": "08686ac6",
            "type": "wpkh",
            "xpub": "tpubDDUotcvrYMUiy4ncDirveTfhmvggdj8nxcW5JgHpGzYz3UVscJY5aEzFvgUPk4YyajadBnsTBmE2YZmAtJC14Q21xncJgVaHQ7UdqMRVRbU"
        },
        {
            "derivation": "m/84h/1h/1h",
            "original": "vpub5ZSem3mLXiSK55jPzfLVhbHbTEwGzEFZv3xrGFCw1vGHSNw7WcVuJXysJLWcgENQd3iXSNQaeSXUBW55Hy4GAjSTjrWP4vpKKkUN9jiU1Tc",
            "fingerprint": "08686ac6",
            "type": "wpkh",
            "xpub": "tpubDDUotcvrYMUj3UJV7ZtqKgoy8JKprrjdHubbBb3r7qmwHsEH69g7h6xyanWaCYdVEEV3Yu7a6s4ceFnp8DjXeeFxY8eXvH7XTAC4gxfDNEW"
        },
        {
            "derivation": "m/84h/1h/2h",
            "original": "vpub5ZSem3mLXiSK64v64deytnDCoYqbUSYHvmVurUGVMEnXMyEybtF3FEnNuiFDDC6J18a81fv5ptQXaQaaRiYx8MRxahipgxPLdxubpYt1dkD",
            "fingerprint": "08686ac6",
            "type": "wpkh",
            "xpub": "tpubDDUotcvrYMUj4TVBBYDKWsjaUcE9M52MJd8emp7QTAJBDTY9BRRFdomVCAFAjWMNcKLe8Cd5HJwg3AJKFyEDcGFTNyryYJgYmNdJMhwB2RG"
        },
        {
            "derivation": "m/84h/1h/3h",
            "original": "vpub5ZSem3mLXiSK8cKzh4sHxTvN7mgYQA29HfoAZeCDtX1M2zdejN5XVAtVyqhk8eui18JTtZ9M3VD3AiWCz8VwrybhBUh3HxzS8js3mLVybDT",
            "fingerprint": "08686ac6",
            "type": "wpkh",
            "xpub": "tpubDDUotcvrYMUj6zu5oyRdaZSjnq56GnWCfXRuUz38zSWztUvpJuFjsjscGHhheyAncK4z15rLVukBdUDwpPBDLtRBykqC9KHeG9akJWRipKK"
        }
    ]
}
"""
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
    specter = Specter(
        data_folder=devices_filled_data_folder, config=config, checker_threads=False
    )
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

""" A toolkit for hunting flaky tests. For now, this way of running pytest gave more or less consistent
    bad results:
    clear && pytest tests/test_managers_wallet.py tests/test_cli_server.py tests/test_managers_device.py \
        tests/test_managers_wallet.py tests/test_node.py tests/test_node_controller.py tests/test_rest.py

"""

import os
import pytest
import traceback
import threading
import sys
from cryptoadvance.specter.specter_error import (
    BrokenCoreConnectionException,
    SpecterError,
)
from cryptoadvance.specter.process_controller.bitcoind_controller import (
    BitcoindPlainController,
)
from cryptoadvance.specter.rpc import RpcError
from cryptoadvance.specter.specter_error import SpecterError


def should_intercept(call):
    """Should return a boolean whether the visibility output should be done.
    This needs to be more and more restricted overtime as we hopefully
    have less and less flaky tests in the future and the normal output is enough.
    """
    # Modify that manually!
    return False

    # isinstance(call.excinfo.value, RpcError)
    # or isinstance(call.excinfo.value, SpecterError)
    # or isinstance(call.excinfo.value, AssertionError)
    # or isinstance(call.excinfo.value, AttributeError)


@pytest.hookimpl(hookwrapper=True)
def pytest_exception_interact(node, call, report):
    """Making more clever investigations in case of Exceptions"""
    if should_intercept(call):
        print()
        print("IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII")
        print(
            f"intercepting: {call.excinfo.value.__class__.__name__} while {report.when}"
        )
        print_exception(node, call, report)
        print_threaddump(node, call, report)
        print_debug_logs(node, call, report)
        print_directory_content(node, call, report)
        print("IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII")

    yield


def print_exception(node, call, report):
    """prints a stacktrace of the intercepted Exception"""
    print(f"XXXXXXXXXXXXXXXXXX_EXCEPTION_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
    traceback.print_exception(call.excinfo.value)
    print("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")


def print_threaddump(node, call, report):
    """prints a threaddump, a list of stacktraces from all threads"""
    print("XXXXXXXXXXXXXXXXXX_THREADDUMP_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
    for th in threading.enumerate():
        print(th)
        traceback.print_stack(sys._current_frames()[th.ident])
        print()
    print("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")


def print_debug_logs(node, call, report):
    """prints the debug-logs of all the Regtest instances"""
    if isinstance(call.excinfo.value, BrokenCoreConnectionException):
        print("XXXXXXXXXXXXXXXXXX_DEBUG.LOG_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
        regtests = []
        for fixture_name in node.fixturenames:
            regtest = node.funcargs.get(fixture_name)
            if isinstance(regtest, BitcoindPlainController):
                regtests.append(regtest)
        for regtest in regtests:
            print("---------------------------------------------------------")
            print(
                f"{regtest} in DATADIR {regtest.datadir} on PORT {regtest.rpcconn.rpcport}"
            )
            print(regtest.get_debug_log())
        print("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")


def print_directory_content(node, call, report):
    if str(call.excinfo.value).startswith(
        "[Errno 39]"
    ):  # [Errno 39] Directory not empty: '/tmp/specter_home_tmp_vzn6u1rv'
        folder = str(call.excinfo.value).split(":")[1][2:-1]
        print("XXXXXXXXX_DIR_CONTENT_OF_{folder}_XXXXXXXXXXXXXXXXXXXXXXXXXXX")
        for file in os.listdir(folder):
            print(file)
        print("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")

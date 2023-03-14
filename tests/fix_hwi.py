import os

import pytest
import requests
from mock import MagicMock

from cryptoadvance.specterext.hwi.binary_downloader import BinaryDownloader
from cryptoadvance.specterext.hwi.hwi_rpc_binary import HWIBinaryBridge
from cryptoadvance.specterext.hwi.hwi_rpc_hwilib import HWILibBridge


@pytest.fixture()
def hwi_binary():
    specter_mock = MagicMock()
    specter_mock.data_folder = os.path.join("tests")
    specter_mock.requests_session.return_value = requests.Session()
    downloader = BinaryDownloader.from_github_repo(
        specter_mock,
        "2.2.1",
        "301caf48c7bc1dc5e24e28e2818fdeeaf38d6d3ae24ac7229150bf89eaf555be",
    )
    return downloader.get_executable  # returning a function here


# fmt: off
@pytest.fixture(params=[
    HWILibBridge, 
    HWIBinaryBridge
])
# fmt: on
def hwi(request, hwi_binary):
    clazz = request.param
    if clazz == HWIBinaryBridge:
        instance = clazz(hwi_binary)
    else:
        instance = HWILibBridge()
    # There is a bug https://github.com/bitcoin-core/HWI/issues/636 which makes it necessary
    # to pass the device-path for certain commands
    # instance.path = instance.enumerate()["path"]
    return instance

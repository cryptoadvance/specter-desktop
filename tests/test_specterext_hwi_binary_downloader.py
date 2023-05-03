import logging
import time
import os

import requests
from mock import MagicMock

from cryptoadvance.specterext.hwi.binary_downloader import BinaryDownloader


def test_BinaryDownloader(empty_data_folder, caplog):
    caplog.set_level(logging.DEBUG)

    specter_mock = MagicMock()
    specter_mock.data_folder = empty_data_folder
    specter_mock.requests_session.return_value = requests.Session()

    downloader = BinaryDownloader.from_github_repo(
        specter_mock,
        "2.2.1",
        "301caf48c7bc1dc5e24e28e2818fdeeaf38d6d3ae24ac7229150bf89eaf555be",
    )
    for i in range(1, 24):

        print(downloader.status)
        if not downloader._download_thread.is_alive():
            break
        time.sleep(0.5)
    assert downloader.status == "ready"
    assert os.path.isfile(downloader.get_executable())

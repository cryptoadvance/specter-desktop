from cryptoadvance.specter.util.tor_setup_tasks import setup_tor_thread
import mock
import logging
import os
import subprocess


def test_tor_setup_task(caplog, empty_data_folder):
    """This test should work with Linux and MacOS. But it's only tested on
    CICD with Linux
    """
    caplog.set_level(logging.DEBUG)
    spectrum_mock = mock.MagicMock()
    spectrum_mock.data_folder = empty_data_folder
    setup_tor_thread(spectrum_mock)
    print("Files in empty_data_folder")
    for filename in os.listdir(empty_data_folder):
        print(filename)
    print("Files in empty_data_folder/tor-binaries")
    for filename in os.listdir(os.path.join(empty_data_folder, "tor-binaries")):
        print(filename)
    tor_binary = os.path.join(empty_data_folder, "tor-binaries", "tor")
    assert os.path.isfile(tor_binary)
    output = subprocess.check_output([tor_binary, "--version"])
    assert b"Tor version 0.4.8.0" in output
    # assert False

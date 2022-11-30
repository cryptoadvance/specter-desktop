""" The tests in this file are built to intentionally fail in order to test the
    functionality in the conf_visibility pytest plugin
    
    Therefore, the tests are skipped
"""
import os
import pytest
import threading
import time

from cryptoadvance.specter.persistence import write_json_file


def thread_function(empty_data_folder):
    fname = os.path.join(empty_data_folder, "some.file")
    for i in range(0, 100000):
        try:
            with open(fname, "w") as f:
                f.write("muh")
        except FileNotFoundError as e:
            print("---------------------\nFileNotFound Error for i = " + str(i))
            raise e


@pytest.mark.skip
def test_fail(empty_data_folder):
    print(empty_data_folder)

    t = threading.Thread(
        target=thread_function,
        args=(empty_data_folder,),
    )
    t.start()
    time.sleep(0.08)

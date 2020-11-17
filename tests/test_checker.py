import logging
import mock
import time
from mock import Mock
from cryptoadvance.specter.util.checker import Checker


def test_checker(caplog):
    callback_mock = Mock()
    caplog.set_level(logging.DEBUG)
    checker = Checker(lambda: callback_mock(), period=0.01)
    checker.start()
    time.sleep(
        0.1
    )  # If the above assumptions are failing, you might want to increase this
    assert "Checker started" in caplog.text
    assert "This message won't show again until stopped and started." in caplog.text
    checker.stop()
    assert "Checker stopped" in caplog.text
    callback_mock.side_effect = Exception("someException")
    checker.start()
    time.sleep(
        0.8
    )  # If the above assumptions are failing, you might want to increase this
    checker.stop()
    assert "someException" in caplog.text
    assert caplog.text.count("someException") == 5
    assert "The above Error-Message is now suppressed" in caplog.text
    assert caplog.text.count("The above Error-Message is now suppressed") == 1

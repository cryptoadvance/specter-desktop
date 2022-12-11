import logging
import mock
import time
from mock import Mock
from cryptoadvance.specter.util.checker import Checker


def test_checker(caplog):
    callback_mock = Mock()
    caplog.set_level(logging.DEBUG)
    checker = Checker(lambda: callback_mock(), period=0.01, desc="test")
    checker.start()
    time.sleep(
        0.1
    )  # If the above assumptions are failing, you might want to increase this
    assert "Checker test started" in caplog.text
    assert "This message won't show again until stopped and started." in caplog.text
    checker.stop()
    time.sleep(0.01)
    assert "Checker test stopped" in caplog.text
    callback_mock.side_effect = Exception("someException")
    checker.start()
    time.sleep(
        2
    )  # If the above assumptions are failing, you might want to increase this
    checker.stop()
    assert "someException" in caplog.text
    # should output 5 times
    assert caplog.text.count("[   ERROR] Checker ") == 5
    # But should also show stacktrace 5 times
    assert caplog.text.count("Exception: someException") == 5
    assert caplog.text.count("The above Error-Message is from now on suppressed!") == 1

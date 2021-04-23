import os
from cryptoadvance.specter.managers.otp_manager import OtpManager
import time


def test_OtpManager(empty_data_folder):
    # A OtpManager manages Otp, one-time-passwords
    # via json-files in an empty data folder
    otpm = OtpManager(data_folder=empty_data_folder)
    assert os.path.isfile(os.path.join(empty_data_folder, "otps.json"))
    # initialization will load from the folder but it's empty at first
    assert otpm.data == {}  # but you shouldn't access data directly anyway
    # an otp looks like this:
    an_otp = {
        "otp": "aOxO42IeM-aRB4WjBIAQRA",
        "created_at": 1618491877.546648,
        "expiry": 1617495477.546648,
    }
    otpm.add_new_user_otp(an_otp)
    yet_another_otp = {
        "otp": "nPfouONJmUgS642MitqPkg",
        "created_at": time.time(),
        "expiry": time.time() + 60 * 60,  # plus 1 h
    }
    assert otpm.validate_new_user_otp(an_otp["otp"]) == False
    otpm.add_new_user_otp(yet_another_otp)
    assert otpm.validate_new_user_otp(an_otp["otp"]) == False
    assert otpm.validate_new_user_otp(yet_another_otp["otp"]) == True
    otpm.remove_new_user_otp(an_otp["otp"])
    # If it doesn't exist, False as well
    assert otpm.validate_new_user_otp(an_otp["otp"]) == False
    # anything gets you False
    assert otpm.validate_new_user_otp("anything") == False

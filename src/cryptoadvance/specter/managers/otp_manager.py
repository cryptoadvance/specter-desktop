import os
import time

from ..persistence import read_json_file, write_json_file
from .genericdata_manager import GenericDataManager


class OtpManager(GenericDataManager):
    """
    The OtpManager manages otps (one time passwords) in otps.json
    """

    initial_data = {}
    name_of_json_file = "otps.json"

    def add_new_user_otp(self, otp_dict):
        """adds an OTP for user registration"""
        if "new_user_otps" not in self.data:
            self.data["new_user_otps"] = []
        self.data["new_user_otps"].append(otp_dict)
        self._save()

    def validate_new_user_otp(self, otp):
        """validates an OTP for user registration and removes it if expired"""
        if "new_user_otps" not in self.data:
            return False
        now = time.time()
        for i, otp_dict in enumerate(self.data["new_user_otps"]):
            if otp_dict["otp"] == otp:
                if (
                    "expiry" in otp_dict
                    and otp_dict["expiry"] < now
                    and otp_dict["expiry"] > 0
                ):
                    del self.data["new_user_otps"][i]
                    self._save()
                    return False
                return True
        return False

    def remove_new_user_otp(self, otp):
        """removes an OTP for user registration"""
        if "new_user_otps" not in self.data:
            return False
        for i, otp_dict in enumerate(self.data["new_user_otps"]):
            if otp_dict["otp"] == otp:
                del self.data["new_user_otps"][i]
                self._save()
                return True
        return False

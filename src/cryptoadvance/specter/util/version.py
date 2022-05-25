import subprocess
import sys
import logging
import re
import threading
import time
import os
from urllib.error import HTTPError
import requests
from requests.exceptions import ConnectionError
from urllib3.exceptions import NewConnectionError
import importlib_metadata

from cryptoadvance.specter.specter_error import SpecterError

logger = logging.getLogger(__name__)


class VersionChecker:
    def __init__(self, name="cryptoadvance.specter", specter=None):
        self.name = name

        self.current = self._get_current_version()
        self.latest = "unknown"
        self.upgrade = False
        self.running = False
        self.specter = specter

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.loop)
            self.thread.daemon = True
            self.thread.start()

    def stop(self):
        logger.info("version checker stopped.")
        self.running = False

    @property
    def info(self):
        info = {"current": self.current, "latest": self.latest, "upgrade": self.upgrade}
        return info

    @property
    def installation_type(self):
        """app or pip"""
        if getattr(sys, "frozen", False):
            return "app"
        else:
            return "pip"

    def loop(self, dt=3600):
        """Checks for updates once per hour"""
        while self.running:
            self.current, self.latest, self.upgrade = self.get_version_info()
            logger.info(
                f"version checked, install_type {self.installation_type} curr: {self.current} latest: {self.latest} ==> upgrade: {self.upgrade}"
            )
            time.sleep(dt)

    def _get_current_version(self):
        current = "unknown"
        if self.installation_type == "app":
            current = VersionChecker._version_txt_content()
        else:
            current = importlib_metadata.version(self.name)
            if current == None:
                current = "custom"
        if current == "vx.y.z-get-replaced-by-release-script":
            current = "custom"
        return current

    def _get_binary_version(self):
        """
        Get binary version: current, latest.
        Fails if version.txt is not present.
        Returns latest = "unknown" if fetch failed.
        """
        current = self._get_current_version()
        latest = "unknown"
        if self.name != "cryptoadvance.specter":
            logger.warning(
                "We're checking here for a different binary than specter-desktop. We're hopefully in a pytest"
            )
        latest = self._get_latest_version_from_github()
        return current, latest

    def _get_pip_version(self):
        """
        returns current, latest
        """
        current = self._get_current_version()
        latest = "unknown"
        try:
            if self.specter:
                requests_session = self.specter.requests_session(force_tor=False)
            else:
                requests_session = requests.Session()

            releases = (
                requests_session.get(f"https://pypi.org/pypi/{self.name}/json")
                .json()["releases"]
                .keys()
            )
            releases = list(releases)
            for i in range(-1, 0 - len(releases), -1):
                # for some stupid reason, rc-versions are BEFORE the real versions
                if not releases[i][:-1].endswith("rc"):
                    latest = releases[i]
                    break
        except (
            HTTPError,
            ConnectionError,
            ConnectionRefusedError,
            NewConnectionError,
        ) as e:
            logger.error(f"{e} while checking for new pypi version")
        except Exception as e:
            logger.exception(e)
            latest = "unknown"
        return current, latest

    def get_version_info(self):
        """
        Returns a triple of the current version
        of the pip-package cryptoadvance.specter and
        the latest version and whether you should upgrade.
        """
        # check if we have version.txt file
        # this is the case for binaries
        current = "unknown"
        latest = "unknown"
        # check binary version
        if self.installation_type == "app":
            current, latest = self._get_binary_version()
        else:
            current, latest = self._get_pip_version()

        # check that both current and latest versions match the pattern
        # vA.B.C or just A.B.C
        # For vA.B.C-preX or something like that we don't show notification
        if re.search(r"v?([\d+]).([\d+]).([\d+])$", current):
            if re.search(r"v?([\d+]).([\d+]).([\d+])$", latest):
                return (
                    current,
                    latest,
                    # check without leading v so v1.2.3 = 1.2.3
                    latest.replace("v", "") != current.replace("v", ""),
                )
        # if current version is not A.B.C - stop periodic checks
        else:
            self.stop()
        return current, latest, False

    def _get_latest_version_from_github(self):
        try:
            if self.specter:
                requests_session = self.specter.requests_session(force_tor=False)
            else:
                requests_session = requests.Session()
            print(requests_session.get().json())
            releases = (
                requests_session.get(f"https://pypi.org/pypi/{self.name}/json")
                .json()["releases"]
                .keys()
            )
            latest = list(releases)[-1]
        except Exception as e:
            logger.exception(e)
            latest = "unknown"
        return latest

    @classmethod
    def _version_txt_content(cls):
        version_file = "version.txt"
        if getattr(sys, "frozen", False):
            version_file = os.path.join(sys._MEIPASS, "version.txt")
        with open(version_file) as f:
            return f.read().strip()


def compare(version1: str, version2: str) -> int:
    """Compares two version strings like v1.5.1 and v1.6.0 and returns
    * 1 : version2 is bigger that version1
    * -1 : version1 is bigger than version2
    * 0 : both are the same
    This is not supporting semver and it doesn't take any postfix (-pre5)
    into account and is therefore a naive implementation
    """
    version1 = _parse_version(version1)
    version2 = _parse_version(version2)

    if version1["postfix"] != "" or version2["postfix"] != "":
        raise SpecterError(
            f"Cannot compare if either version has a postfix : {version1} and {version2}"
        )
    if version1["major"] > version2["major"]:
        return -1
    elif version1["major"] < version2["major"]:
        return 1
    if version1["minor"] > version2["minor"]:
        return -1
    elif version1["minor"] < version2["minor"]:
        return 1
    if version1["patch"] > version2["patch"]:
        return -1
    elif version1["patch"] < version2["patch"]:
        return 1
    return 0


def _parse_version(version: str) -> dict:
    """Parses version-strings like v1.5.6-pre5 and returns a dict"""
    if version[0] != "v":
        raise SpecterError(f"version {version} does not have a preceding 'v'")
    version = version[1:]
    version_ar = version.split(".")
    if len(version_ar) != 3:
        raise SpecterError(f"version {version} does not have 3 separated digits")
    postfix = ""
    if "-" in version_ar[2]:
        postfix = version_ar[2].split("-")[1]
        version_ar[2] = version_ar[2].split("-")[0]
    return {
        "major": int(version_ar[0]),
        "minor": int(version_ar[1]),
        "patch": int(version_ar[2]),
        "postfix": postfix,
    }

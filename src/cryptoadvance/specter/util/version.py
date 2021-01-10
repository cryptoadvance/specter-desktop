import subprocess
import sys
import logging
import re
import threading
import time
import os
import requests
import importlib_metadata

logger = logging.getLogger(__name__)


class VersionChecker:
    def __init__(self, name="cryptoadvance.specter", specter=None):
        self.name = name
        self.current = self.get_current_version()
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
        return {"current": self.current, "latest": self.latest, "upgrade": self.upgrade}

    def loop(self, dt=3600):
        """Checks for updates once per hour"""
        while self.running:
            self.current, self.latest, self.upgrade = self.get_version_info()
            logger.info(f"version checked. upgrade: {self.upgrade}")
            time.sleep(dt)

    def get_current_version(self):
        current = "unknown"
        try:
            # try binary file
            version_file = "version.txt"
            if getattr(sys, "frozen", False):
                version_file = os.path.join(sys._MEIPASS, "version.txt")
            with open(version_file) as f:
                current = f.read().strip()
        except:
            try:
                current = importlib_metadata.version("cryptoadvance.specter")
                # check if it's installed from master
                if current == "vx.y.z-get-replaced-by-release-script":
                    current = "custom"
            except:
                pass
        return current

    def get_binary_version(self):
        """
        Get binary version: current, latest.
        Fails if version.txt is not present.
        Returns latest = "unknown" if fetch failed.
        """
        version_file = "version.txt"
        if getattr(sys, "frozen", False):
            version_file = os.path.join(sys._MEIPASS, "version.txt")
        with open(version_file) as f:
            current = f.read().strip()
        try:
            if self.specter:
                requests_session = self.specter.requests_session(force_tor=False)
            else:
                requests_session = requests.Session()
            releases = requests_session.get(
                "https://api.github.com/repos/cryptoadvance/specter-desktop/releases"
            ).json()
            latest = "unknown"
            for release in releases:
                if release["prerelease"] or release["draft"]:
                    continue
                latest = release["name"]
                break
        except:
            latest = "unknown"
        return current, latest

    def get_pip_version(self):
        if self.specter:
            requests_session = self.specter.requests_session(force_tor=False)
        else:
            requests_session = requests.Session()
        try:
            releases = (
                requests_session.get("https://pypi.org/pypi/cryptoadvance.specter/json")
                .json()["releases"]
                .keys()
            )

            latest = list(releases)[-1]
        except:
            latest = "unknown"

        current = importlib_metadata.version("cryptoadvance.specter")
        # check if it's installed from master
        if current == "vx.y.z-get-replaced-by-release-script":
            current = "custom"

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
        try:
            current, latest = self.get_binary_version()
        # if file not found
        except FileNotFoundError as exc:
            try:
                current, latest = self.get_pip_version()
            except Exception as exc:
                logger.error(exc)
        # other exceptions
        except Exception as exc:
            logger.error(exc)

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

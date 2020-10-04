import subprocess
import sys
import logging
import re
import threading
import time
import os
import requests

logger = logging.getLogger(__name__)


class VersionChecker:
    def __init__(self, name="cryptoadvance.specter"):
        self.name = name
        self.current = "unknown"
        self.latest = "unknown"
        self.upgrade = False
        self.running = False

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.loop)
            self.thread.daemon = True
            self.thread.start()

    def stop(self):
        self.running = False

    @property
    def info(self):
        return {
            "current": self.current,
            "latest": self.latest,
            "upgrade": self.upgrade,
        }

    def loop(self, dt=3600):
        """Checks for updates once per hour"""
        while self.running:
            self.current, self.latest, self.upgrade = self.get_version_info()
            logger.info(f"version checked. upgrade: {self.upgrade}")
            time.sleep(dt)

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
            releases = requests.get(
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
        latest = str(
            subprocess.run(
                [sys.executable, "-m", "pip", "install", f"{self.name}==random"],
                capture_output=True,
                text=True,
            )
        )
        latest = latest[latest.find("(from versions:") + 15 :]
        latest = latest[: latest.find(")")]
        latest = latest.replace(" ", "").split(",")[-1]

        current = str(
            subprocess.run(
                [sys.executable, "-m", "pip", "show", f"{self.name}"],
                capture_output=True,
                text=True,
            )
        )
        current = current[current.find("Version:") + 8 :]
        current = current[: current.find("\\n")].replace(" ", "")
        # master?
        if current == "vx.y.z-get-replaced-by-release-script":
            current = "custom"
            # no need to check upgrades
            self.running = False
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
        if re.search(r"v?([\d+]).([\d+]).([\d+]).*", current) and re.search(
            r"v?([\d+]).([\d+]).([\d+]).*", latest
        ):
            return (
                current,
                latest,
                # check without leading v so v1.2.3 = 1.2.3
                latest.replace("v", "") != current.replace("v", ""),
            )
        return current, latest, False

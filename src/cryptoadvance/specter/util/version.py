import subprocess
import sys
import logging
import re
import threading
import time

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

    def get_version_info(self):
        '''
        Returns a triple of the current version
        of the pip-package cryptoadvance.specter and
        the latest version and whether you should upgrade.
        '''
        try:
            # fail right away if it's a binary
            if getattr(sys, 'frozen', False):
                # no need to check upgrades
                self.running = False
                return "binary", "binary", False
            latest_version = str(subprocess.run([
                sys.executable, '-m', 'pip',
                'install', f'{self.name}==random'],
                capture_output=True, text=True))
            latest_version = latest_version[latest_version.find(
                '(from versions:')+15:]
            latest_version = latest_version[:latest_version.find(')')]
            latest_version = latest_version.replace(' ', '').split(',')[-1]

            current_version = str(subprocess.run([
                sys.executable, '-m', 'pip',
                'show', f'{self.name}'],
                capture_output=True, text=True))
            current_version = current_version[current_version.find(
                'Version:')+8:]
            current_version = current_version[:current_version.find(
                '\\n')].replace(' ', '')
            # master?
            if current_version == 'vx.y.z-get-replaced-by-release-script':
                current_version = 'custom'
                # no need to check upgrades
                self.running = False

            # check that both current and latest versions match the pattern
            if (re.search(r"v?([\d+]).([\d+]).([\d+]).*", current_version) and
                    re.search(r"v?([\d+]).([\d+]).([\d+]).*", latest_version)):
                return (current_version,
                        latest_version,
                        latest_version != current_version)
            return current_version, latest_version, False
        except Exception as exc:
            # if pip is not installed or we are using python3.6 or below
            # we just don't show the version
            logger.error(exc)
            return "unknown", "unknown", False

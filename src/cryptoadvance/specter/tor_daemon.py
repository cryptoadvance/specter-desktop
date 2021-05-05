import logging
import subprocess
import platform
import os
import signal
import psutil

logger = logging.getLogger(__name__)


class TorDaemonController:
    """A class controlling the tor-daemon process directly on the machine"""

    def __init__(
        self,
        tor_daemon_path,
        tor_config_path,
    ):
        self.tor_daemon_path = tor_daemon_path
        self.tor_config_path = tor_config_path
        self.tor_daemon_proc = None

    def start_tor_daemon(self, cleanup_at_exit=True):
        if self.is_running():
            return

        self.tor_daemon_proc = subprocess.Popen(
            f'{"exec " if platform.system() != "Windows" else ""}"{self.tor_daemon_path}" --defaults-torrc {self.tor_config_path}',
            shell=True,
        )
        logger.debug(
            "Running tor-daemon process with pid {}".format(self.tor_daemon_proc.pid)
        )

    def get_hashed_password(self, password):
        hashed_pw = subprocess.check_output(
            f'{"exec " if platform.system() != "Windows" else ""}"{self.tor_daemon_path}" --hash-password {password}',
            shell=True,
        ).decode("utf8")

        if not hashed_pw.startswith("16:"):
            return "16:" + hashed_pw.split("\n16:")[1]
        return hashed_pw

    def is_running(self):
        return self.tor_daemon_proc and self.tor_daemon_proc.poll() is None

    def stop_tor_daemon(self):
        timeout = 50  # in secs
        if self.tor_daemon_proc:
            if platform.system() == "Windows":
                subprocess.run("Taskkill /IM tor.exe /F")
            self.tor_daemon_proc.terminate()
            procs = psutil.Process().children()
            for p in procs:
                p.terminate()
            _, alive = psutil.wait_procs(procs, timeout=timeout)
            for p in alive:
                logger.info("tor daemon did not terminated in time, killing!")
                p.kill()

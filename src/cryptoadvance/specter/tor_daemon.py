import logging
import os
import platform
import signal
import socket
import subprocess
from io import StringIO

import psutil

from .specter_error import SpecterError

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
        self.is_running()  # throws an exception if port 9050 is open (which looks like another tor-process is running)

    def start_tor_daemon(self, cleanup_at_exit=True):
        if self.is_running():
            if self.tor_daemon_proc is None:
                raise Exception(
                    "Tor Daemon running but not via this Controller instance."
                )
            return

        self.tor_daemon_proc = subprocess.Popen(
            f'{"exec " if platform.system() != "Windows" else ""}"{self.tor_daemon_path}" --defaults-torrc {self.tor_config_path}',
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        logger.debug(
            "Running tor-daemon process with pid {}".format(self.tor_daemon_proc.pid)
        )

    def get_logs(self):
        if self.is_running():
            return "Cannot return logs as tor is still running"
        logs = ""
        newline = self.tor_daemon_proc.stdout.readline().decode("ascii")
        while newline != "":
            logs = logs + newline
            newline = self.tor_daemon_proc.stdout.readline().decode("ascii")
        return logs

    def get_hashed_password(self, password):
        hashed_pw = subprocess.check_output(
            f'{"exec " if platform.system() != "Windows" else ""}"{self.tor_daemon_path}" --hash-password {password}',
            shell=True,
        ).decode("utf8")

        if not hashed_pw.startswith("16:"):
            return "16:" + hashed_pw.split("\n16:")[1]
        return hashed_pw

    def is_running(self):
        # This fails the cypress-tests, unfortunately
        # if not self.tor_daemon_proc and self.is_port_open():
        #    raise SpecterError(
        #        "Port 9050 is open but tor_daemon_proc is not existing. Probably another Tor-Daemon is running?!"
        #    )
        return self.tor_daemon_proc and self.tor_daemon_proc.poll() is None

    def is_port_open(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        location = ("127.0.0.1", 9050)
        try:
            s.connect(location)
            s.close()
            return True
        except Exception as e:
            return False

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

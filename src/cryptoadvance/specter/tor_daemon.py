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
    """A class controlling the Tor daemon process directly on the machine"""

    def __init__(
        self,
        tor_daemon_path,
        tor_config_path,
    ):
        self.tor_daemon_path = tor_daemon_path
        self.tor_config_path = tor_config_path
        self.tor_daemon_proc = None
        self.is_running()

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
            "Running Tor daemon process with pid {}".format(self.tor_daemon_proc.pid)
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
        """Checks whether the Tor process is still running.
        Note: poll() from the subprocess module does not work reliably. For example,
        if the process has been terminated but its exit code has not yet been collected, it would still indicate
        that the process is still running.
        """
        if self.tor_daemon_proc is None:
            return False
        try:
            # Note: This pid here is usually not the same as the pid given by the OS to the Tor process
            process = psutil.Process(self.tor_daemon_proc.pid)
            logger.debug(f"Is the built-in Tor daemon running? {process.is_running()}")
            return process.is_running()
        except psutil.NoSuchProcess:
            return False

    # Currently not used
    def is_port_open(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        location = ("127.0.0.1", 9050)
        try:
            s.connect(location)
            s.close()
            return True
        except Exception as e:
            logger.exception(e)
            return False

    def stop_tor_daemon(self):
        # It is possible for the Tor process to terminate unexpectedly without updating self.tor_daemon_proc
        if not self.is_running():
            return
        if self.tor_daemon_proc:
            # This double approach ensures that the Tor child process is terminated on all levels (within Specter and on the OS level).
            # This seems to be unnecessary for Linux, but it is necessary for MacOS and Windows.
            if platform.system() == "Windows":
                subprocess.run("Taskkill /IM tor.exe /F")
            else:
                cmdline_args = f"{self.tor_daemon_path} --defaults-torrc {self.tor_config_path}"  # Sth. like: ~/.specter/tor-binaries/tor --defaults-torrc ~/.specter/torrc
                subprocess.run(["pkill", "-f", cmdline_args])
            self.tor_daemon_proc.terminate()
            self.tor_daemon_proc = None

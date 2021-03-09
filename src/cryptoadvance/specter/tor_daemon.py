import logging
import subprocess

logger = logging.getLogger(__name__)


class TorDaemonController:
    """ A class controlling the tor-daemon process directly on the machine """

    def __init__(
        self,
        tor_daemon_path,
        tor_config_path,
    ):
        self.tor_daemon_path = tor_daemon_path
        self.tor_config_path = tor_config_path
        self.tor_daemon_proc = None

    def start_tor_daemon(self, cleanup_at_exit=True):
        if self.tor_daemon_proc != None:
            return self.tor_daemon_proc
        # exec will prevent creating a child-process and will make tor_daemon_proc.terminate() work as expected
        self.tor_daemon_proc = subprocess.Popen(
            f'exec "{self.tor_daemon_path}" --defaults-torrc {self.tor_config_path}',
            shell=True,
        )
        logger.debug(
            "Running tor-daemon process with pid {}".format(self.tor_daemon_proc.pid)
        )

    def get_hashed_password(self, password):
        if self.tor_daemon_proc != None:
            return self.tor_daemon_proc
        # exec will prevent creating a child-process and will make tor_daemon_proc.terminate() work as expected
        p = subprocess.Popen(
            f'exec "{self.tor_daemon_path}" --hash-password {password}',
            shell=True,
            stdout=subprocess.PIPE,
        )
        return p.stdout.read().decode("utf8")

    def is_running(self):
        return self.tor_daemon_proc and self.tor_daemon_proc.poll() is None

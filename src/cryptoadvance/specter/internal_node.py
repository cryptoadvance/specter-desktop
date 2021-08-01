import logging
import os
import psutil

from .helpers import is_testnet
from .specter_error import SpecterError, ExtProcTimeoutException
from .rpc import (
    get_default_datadir,
)
from .process_controller.bitcoind_controller import BitcoindPlainController
from .persistence import write_node
from .node import Node

logger = logging.getLogger(__name__)


class InternalNode(Node):
    """A Node but other than Node, this one is managed by Specter.
    So it has start and stop methods and one called is_bitcoind_running
    """

    # Possible Stati
    BROKEN = "Broken"
    DOWN = "Down"
    RUNNING = "Running"

    def __init__(
        self,
        name,
        alias,
        autodetect,
        datadir,
        user,
        password,
        port,
        host,
        protocol,
        fullpath,
        manager,
        bitcoind_path,
        bitcoind_network,
        version,
    ):
        super().__init__(
            name,
            alias,
            autodetect,
            datadir,
            user,
            password,
            port,
            host,
            protocol,
            False,
            fullpath,
            manager,
        )

        self.bitcoind_path = bitcoind_path
        self.bitcoind_network = bitcoind_network
        self._bitcoind = None
        self.version = version
        self._status = self.DOWN
        if self.bitcoind_network != "main":
            if self.bitcoind_network == "testnet" and not self.datadir.endswith(
                "/testnet3"
            ):
                self.datadir = os.path.join(self.datadir, "testnet3")
            elif self.bitcoind_network == "regtest" and not self.datadir.endswith(
                "/regtest"
            ):
                self.datadir = os.path.join(self.datadir, "regtest")
            elif self.bitcoind_network == "signet" and not self.datadir.endswith(
                "/signet"
            ):
                self.datadir = os.path.join(self.datadir, "signet")
            logger.info(f"persisting {self} in __init__")
            write_node(self, self.fullpath)

    @classmethod
    def from_json(cls, node_dict, manager, default_alias="", default_fullpath=""):
        name = node_dict.get("name", "")
        alias = node_dict.get("alias", default_alias)
        autodetect = node_dict.get("autodetect", True)
        datadir = node_dict.get("datadir", get_default_datadir())
        user = node_dict.get("user", "")
        password = node_dict.get("password", "")
        port = node_dict.get("port", None)
        host = node_dict.get("host", "localhost")
        protocol = node_dict.get("protocol", "http")
        external_node = node_dict.get("external_node", True)
        fullpath = node_dict.get("fullpath", default_fullpath)
        bitcoind_path = node_dict.get("bitcoind_path", "")
        bitcoind_network = node_dict.get("bitcoind_network", "main")
        version = node_dict.get("version", "")

        return cls(
            name,
            alias,
            autodetect,
            datadir,
            user,
            password,
            port,
            host,
            protocol,
            fullpath,
            manager,
            bitcoind_path,
            bitcoind_network,
            version,
        )

    @property
    def json(self):
        node_json = super().json
        node_json["bitcoind_path"] = self.bitcoind_path
        node_json["bitcoind_network"] = self.bitcoind_network
        node_json["version"] = self.version
        return node_json

    def start(self, timeout=15):
        """Failsafe way to start an internal node."""
        potential_bitcoind_process = BitcoindProcess.by_password(self.password)
        if potential_bitcoind_process:
            logger.info(
                f"Skipping start of internal node, existing one found {potential_bitcoind_process}"
            )
            self.bitcoind.attach_to_proc_id(potential_bitcoind_process)
            self._status = self.RUNNING
            return self.update_rpc()
        try:
            logger.info(f"STARTING bitcoind {self.name} from status {self.status}")
            self.bitcoind.start_bitcoind(
                datadir=os.path.expanduser(self.datadir),
                timeout=timeout,  # At the initial startup, we don't wait on bitcoind
            )
            self._status = self.RUNNING
        except ExtProcTimeoutException as e:
            logger.error(e)
            e.check_logfile(os.path.join(self.datadir, "debug.log"))
            self._status = self.BROKEN
            logger.error(e.get_logger_friendly())
        except SpecterError as e:
            self._status = self.BROKEN
            logger.error(e)
            # Likely files of bitcoind were not found. Maybe deleted by the user?
        logger.info(f"STARTUP process complete {self.name} to status {self.status}")
        return self.update_rpc()

    def _update_status(self, bitcoin, status):
        self._bitcoin = bitcoin
        self._status = status

    def stop(self):
        logger.info(f"STOPPING bitcoind {self.name} from status {self.status}")
        success = self._bitcoind.stop_bitcoind()
        if success:
            self._update_status(None, self.DOWN)
            logger.info(f"bitcoind {self.name} stopped")
        else:
            logger.error(f"Failed to stop bitcoind {self.name}")
            self._status = self.BROKEN
        logger.info(f"STOPPING process complete {self.name} to status {self.status}")

    @property
    def bitcoind(self):
        if os.path.isfile(self.bitcoind_path):
            if not self._bitcoind:
                self._bitcoind = BitcoindPlainController(
                    bitcoind_path=self.bitcoind_path,
                    rpcport=self.port,
                    network=self.bitcoind_network,
                    rpcuser=self.user,
                    rpcpassword=self.password,
                )
            return self._bitcoind
        raise SpecterError(
            "Bitcoin Core files missing. Make sure Bitcoin Core is installed within Specter"
        )

    @property
    def status(self):
        """RUNNING DOWN or BROKEN."""
        return self._status

    def is_bitcoind_running(self):
        if self._status == self.RUNNING:
            return self._bitcoind and self._bitcoind.check_existing()
        return False

    @classmethod
    def kill_process(cls, proc_id):
        try:
            proc = psutil.Process(proc_id)
            proc.terminate()
            # os.kill(proc_id, signal.SIGTERM)
        except ProcessLookupError:
            logger.error("Process with ID {proc_id} does not exist")


class BitcoindProcess:
    """This is a class which represents a Bitcoind-process which is detected out of the context it has been created
    it wraps a Process and therefore behaves like one. At least until it doesn't
    """

    def __init__(self, pid):
        self.pid = pid
        self.proc = psutil.Process(self.pid)

    @classmethod
    def by_password(cls, password):
        """returns a BitcoindProcess which fits the rpcpassword == password"""
        pid = cls.get_process_id(password)
        if not pid is None:
            return BitcoindProcess(pid)
        return None

    def terminate(self):
        try:
            self.proc.terminate()
        except ProcessLookupError:
            logger.error("Process with ID {proc_id} does not exist")

    def kill(self):
        self.proc.kill()

    def poll(self):
        return self.proc.poll()

    def get_cmd_arg_value(self, arg_key):
        """parses the cmdline of the bitcoind-cmd and returns the value to the corresponding key
        e.g. for -rpcpassword=secret
        get_cmd_arg_value("rpcpassword") == "secret"
        """
        for cmd_arg in self.proc.cmdline():
            if cmd_arg.startswith(f"-{arg_key}"):
                arg_value = cmd_arg.split("=")[1]
                return arg_value

    def __repr__(self) -> str:
        return f"<BitcoindProcess datadir={self.get_cmd_arg_value('datadir')} rpcport={self.get_cmd_arg_value('rpcport')} >"

    @classmethod
    def get_process_id(cls, searched_password):
        for proc in psutil.process_iter():
            # logger.debug(f"investigating {proc.name()}")
            try:
                # Get process name & pid from process object.
                if not proc.name().endswith("bitcoind"):
                    continue
                if not proc.exe().endswith("/bitcoin-binaries/bin/bitcoind"):
                    continue
                password = None
                for cmd_arg in proc.cmdline():
                    if cmd_arg.startswith("-rpcpassword"):
                        password = cmd_arg.split("=")[1]
                if searched_password == password:
                    logger.debug(
                        f"Found internal_node bitcoind process with the password given: {proc.pid}"
                    )
                    return proc.pid
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # processes are volatile
                pass
        return None

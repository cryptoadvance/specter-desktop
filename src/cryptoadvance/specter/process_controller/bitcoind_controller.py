from .node_controller import NodePlainController
import atexit
import logging
import signal

logger = logging.getLogger(__name__)


class BitcoindPlainController(NodePlainController):
    """A Controller specifically for the Bitcoind-process"""

    def __init__(
        self,
        bitcoind_path="bitcoind",
        rpcport=18443,
        network="regtest",
        rpcuser="bitcoin",
        rpcpassword="secret",
    ):
        # Just call super and add the node_impl
        super().__init__(
            "bitcoin",
            node_path=bitcoind_path,
            rpcport=rpcport,
            network=network,
            rpcuser=rpcuser,
            rpcpassword=rpcpassword,
        )

    def start_bitcoind(
        self,
        cleanup_at_exit=False,
        cleanup_hard=False,
        datadir=None,
        extra_args=[],
        timeout=60,
    ):
        """starts bitcoind with a specific rpcport=18543 by default.
        That's not the standard in order to make pytest running while
        developing locally against a different regtest-instance
        if bitcoind_path == docker, it'll run bitcoind via docker.
        Specify a longer timeout for slower devices (e.g. Raspberry Pi)
        """
        # convenience method
        return self.start_node(
            cleanup_at_exit,
            cleanup_hard,
            datadir,
            extra_args,
            timeout,
        )

    def attach_to_proc_id(self, bitcoind_process):
        """This assumes that the calling context (prob. a internal_node instance) found a process which is suited.
        So instead of starting, we're somehow faking a start.
        This behaviour should be explicitely triggered as the management of that should be duty of InternalNode
        """
        # avoid circular reference
        from ..internal_node import BitcoindProcess

        self.datadir = bitcoind_process.get_cmd_arg_value("datadir")
        self.node_proc = bitcoind_process
        self.cleanup_hard = (
            False  # assuming an internal node which should not get killed -9
        )

        def cleanup_node_callback(signal_number=None, stack=None):
            self.cleanup_node(False, self.datadir)

        atexit.register(cleanup_node_callback)
        # This is for CTRL-C --> SIGINT
        signal.signal(signal.SIGINT, cleanup_node_callback)
        # This is for kill $pid --> SIGTERM
        signal.signal(signal.SIGTERM, cleanup_node_callback)

        self.status = "Running"

    def stop_bitcoind(self):
        return self.stop_node()

    def version(self):
        """Returns the version of bitcoind, e.g. "v0.19.1" """
        version = self.get_rpc().getnetworkinfo()["subversion"]
        version = version.replace("/", "").replace("Satoshi:", "v")
        return version

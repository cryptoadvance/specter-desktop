from .node_controller import NodePlainController
import logging

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

    def stop_bitcoind(self):
        self.stop_node()

    def version(self):
        """Returns the version of bitcoind, e.g. "v0.19.1" """
        version = self.get_rpc().getnetworkinfo()["subversion"]
        version = version.replace("/", "").replace("Satoshi:", "v")
        return version

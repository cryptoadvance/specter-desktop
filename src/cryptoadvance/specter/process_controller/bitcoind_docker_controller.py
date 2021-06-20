import logging

# the docker-dependency is special as it's only used with pytest --docker or
# if you manually start bitcoind --docker
# If this fails, you need to pip install the test-requirements
import docker
import os
from .node_controller import Btcd_conn, NodeController
import signal
import time

logger = logging.getLogger(__name__)


class BitcoindDockerController(NodeController):
    """A class specifically controlling a docker-based bitcoind-container"""

    def __init__(self, rpcport=18443, docker_tag="latest"):
        self.btcd_container = None
        super().__init__("bitcoin", rpcport=rpcport)
        self.docker_tag = docker_tag

        if self.detect_bitcoind_container(rpcport) != None:
            rpcconn, btcd_container = self.detect_bitcoind_container(rpcport)
            logger.debug("Detected old container ... deleting it")
            btcd_container.stop()
            btcd_container.remove()

    def start_bitcoind(
        self,
        cleanup_at_exit=False,
        cleanup_hard=False,
        datadir=None,
        extra_args=[],
        timeout=60,
    ):
        self.start_node(
            cleanup_at_exit,
            cleanup_hard,
            datadir,
            extra_args,
            timeout,
        )

    def _start_node(
        self, cleanup_at_exit, cleanup_hard=False, datadir=None, extra_args=[]
    ):
        if datadir != None:
            # ignored
            pass
        bitcoind_path = self.construct_node_cmd(self.rpcconn, extra_args=extra_args)
        dclient = docker.from_env()
        logger.debug("Running (in docker): {}".format(bitcoind_path))
        ports = {
            "{}/tcp".format(self.rpcconn.rpcport - 1): self.rpcconn.rpcport - 1,
            "{}/tcp".format(self.rpcconn.rpcport): self.rpcconn.rpcport,
        }
        logger.debug("portmapping: {}".format(ports))
        image = dclient.images.get(
            "registry.gitlab.com/cryptoadvance/specter-desktop/python-bitcoind:{}".format(
                self.docker_tag
            )
        )
        self.btcd_container = dclient.containers.run(
            image,
            bitcoind_path,
            ports=ports,
            detach=True,
        )

        def cleanup_docker_bitcoind(*args):
            logger.info("Cleaning up bitcoind-docker-container")
            self.btcd_container.stop()
            self.btcd_container.remove()

        if cleanup_at_exit:
            logger.debug(
                "Register function cleanup_docker_bitcoind for SIGINT and SIGTERM"
            )
            # This is for CTRL-C --> SIGINT
            signal.signal(signal.SIGINT, cleanup_docker_bitcoind)
            # This is for kill $pid --> SIGTERM
            signal.signal(signal.SIGTERM, cleanup_docker_bitcoind)

        logger.debug(
            "Waiting for container {} to come up".format(self.btcd_container.id)
        )
        self.wait_for_container()
        rpcconn, _ = self.detect_bitcoind_container(self.rpcconn.rpcport)
        if rpcconn == None:
            raise Exception(
                "Couldn't find container or it died already. Check the logs!"
            )
        else:
            self.rpcconn = rpcconn

        logger.info("Started docker bitcoind")

        return

    def stop_bitcoind(self):
        if self.btcd_container != None:
            self.btcd_container.reload()
            if self.btcd_container.status == "running":
                _, container = self.detect_bitcoind_container(self.rpcconn.rpcport)
                if container == self.btcd_container:
                    self.btcd_container.stop()
                    logger.info("Stopped btcd_container {}".format(self.btcd_container))
                    self.btcd_container.remove()
                    return
        raise Exception("Ambigious Container running")

    def stop_node(self):
        self.stop_bitcoind()

    def check_existing(self):
        """Checks whether self.btcd_container is up2date and not ambigious"""
        if self.btcd_container != None:
            self.btcd_container.reload()
            if self.btcd_container.status == "running":
                rpcconn, container = self.detect_bitcoind_container(
                    self.rpcconn.rpcport
                )
                if container == self.btcd_container:
                    return rpcconn
                raise Exception("Ambigious Container running")
        return None

    @staticmethod
    def search_bitcoind_container(all=False):
        """returns a list of containers which are running bitcoind"""
        d_client = docker.from_env()
        return [
            c
            for c in d_client.containers.list(all)
            if (c.attrs["Config"].get("Cmd") or [""])[0] == "bitcoind"
        ]

    @staticmethod
    def detect_bitcoind_container(with_rpcport):
        """checks all the containers for a bitcoind one, parses the arguments and initializes
        the object accordingly
        returns rpcconn, btcd_container
        """
        d_client = docker.from_env()
        potential_btcd_containers = BitcoindDockerController.search_bitcoind_container()
        if len(potential_btcd_containers) == 0:
            logger.debug(
                "could not detect container. Candidates: {}".format(
                    d_client.containers.list()
                )
            )
            all_candidates = BitcoindDockerController.search_bitcoind_container(
                all=True
            )
            logger.debug(
                "could not detect container. All Candidates: {}".format(all_candidates)
            )
            if len(all_candidates) > 0:
                logger.debug("100 chars of logs of first candidate")
                logger.debug(all_candidates[0].logs()[0:100])
            return None
        for btcd_container in potential_btcd_containers:
            rpcport = int(
                [
                    arg
                    for arg in btcd_container.attrs["Config"]["Cmd"]
                    if "rpcport" in arg
                ][0].split("=")[1]
            )
            if rpcport != with_rpcport:
                logger.debug(
                    "checking port {} against searched port {}".format(
                        type(rpcport), type(with_rpcport)
                    )
                )
                continue
            rpcpassword = [
                arg
                for arg in btcd_container.attrs["Config"]["Cmd"]
                if "rpcpassword" in arg
            ][0].split("=")[1]
            rpcuser = [
                arg for arg in btcd_container.attrs["Config"]["Cmd"] if "rpcuser" in arg
            ][0].split("=")[1]
            if "CI" in os.environ:  # this is a predefined variable in gitlab
                # This works on Linux (direct docker) and gitlab-CI but not on MAC
                ipaddress = btcd_container.attrs["NetworkSettings"]["IPAddress"]
            else:
                # This works on most machines but not on gitlab-CI
                ipaddress = "127.0.0.1"
            rpcconn = Btcd_conn(
                rpcuser=rpcuser,
                rpcpassword=rpcpassword,
                rpcport=rpcport,
                ipaddress=ipaddress,
            )
            logger.info("detected container {}".format(btcd_container.id))
            return rpcconn, btcd_container
        logger.debug("No matching container found")
        return None

    def wait_for_container(self):
        """waits for the docker-container to come up. Times out after 10 seconds"""
        i = 0
        while True:
            ip_address = self.btcd_container.attrs["NetworkSettings"]["IPAddress"]
            if ip_address.startswith("172"):
                self.rpcconn.ipaddress = ip_address
                break
            self.btcd_container.reload()
            time.sleep(0.5)
            i = i + 1
            if i > 20:
                raise Exception("Timeout while starting bitcoind-docker-container!")

    def version(self):
        """Returns the version of bitcoind, e.g. "v0.19.1" """
        version = self.get_rpc().getnetworkinfo()["subversion"]
        version = version.replace("/", "").replace("Satoshi:", "v")
        return version

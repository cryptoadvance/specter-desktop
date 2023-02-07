import os
import pytest
import tempfile

from cryptoadvance.specter.node import Node
from cryptoadvance.specter.managers.node_manager import NodeManager
from cryptoadvance.specter.helpers import is_liquid
from cryptoadvance.specter.specter_error import SpecterError

from mock import MagicMock, call, patch


def test_Node_btc(bitcoin_regtest, trezor_wallet_acc2):
    wallet = trezor_wallet_acc2
    with tempfile.TemporaryDirectory("_some_datafolder_tmp") as data_folder:
        node = Node.from_json(
            {
                "autodetect": False,
                "datadir": "",
                "user": bitcoin_regtest.rpcconn.rpcuser,
                "password": bitcoin_regtest.rpcconn.rpcpassword,
                "port": bitcoin_regtest.rpcconn.rpcport,
                "host": bitcoin_regtest.rpcconn.ipaddress,
                "protocol": "http",
            },
            manager=NodeManager(data_folder=data_folder),
            default_fullpath=os.path.join(data_folder, "a_testfile.json"),
        )
        result = node.test_rpc()

        assert result["tests"]["connectable"] == True
        assert result["tests"]["recent_version"] == True
        assert result["tests"]["credentials"] == True
        assert result["tests"]["wallets"] == True

        node_json = node.json
        del node_json["fullpath"]  # This is very different because of the tempfile
        assert node_json == {
            "name": "",
            "python_class": "cryptoadvance.specter.node.Node",
            "alias": "",
            "autodetect": False,
            "datadir": "",
            "user": "bitcoin",
            "password": "secret",
            "port": 18543,
            "host": "localhost",
            "protocol": "http",
            "node_type": "BTC",
        }

        rpc = node._get_rpc()
        assert rpc.getblockchaininfo()["chain"] == "regtest"
        node.rename("some_new_name")
        assert node.json["name"] == "some_new_name"
        node.check_info()
        assert node.is_configured == True
        assert node.is_running == True
        assert node.is_testnet == True
        print(f"info = {node.info}")
        # something like:
        # {'chain': 'regtest', 'blocks': 100, 'headers': 100, 'bestblockhash': '5277c27b3b5e8aad8e079a928e4675931ea1638a28c7a33bae4ef26425402259', 'difficulty': 4.656542373906925e-10, 'mediantime': 1622635607, 'verificationprogress': 1, 'initialblockdownload': False, 'chainwork': '00000000000000000000000000000000000000000000000000000000000000ca', 'size_on_disk': 30477, 'pruned': False, 'softforks': {'bip34': {'type': 'buried', 'active': False, 'height': 500}, 'bip66': {'type': 'buried', 'active': False, 'height': 1251}, 'bip65': {'type': 'buried', 'active': False, 'height': 1351}, 'csv': {'type': 'buried', 'active': False, 'height': 432}, 'segwit': {'type': 'buried', 'active': True, 'height': 0}, 'testdummy': {'type': 'bip9', 'bip9': {'status': 'defined', 'start_time': 0, 'timeout': 9223372036854775807, 'since': 0}, 'active': False}}, 'warnings': '', 'mempool_info': {'loaded': True, 'size': 0, 'bytes': 0, 'usage': 0, 'maxmempool': 300000000, 'mempoolminfee': 1e-05, 'minrelaytxfee': 1e-05}, 'uptime': 480, 'blockfilterindex': False, 'utxorescan': None}
        chain = node.info["chain"]
        assert chain == "regtest"
        assert is_liquid(chain) == False

        print(f"network_info = {node.network_info}")
        # something like:
        # {'version': 200100, 'subversion': '/Satoshi:0.20.1/', 'protocolversion': 70015, 'localservices': '0000000000000409', 'localservicesnames': ['NETWORK', 'WITNESS', 'NETWORK_LIMITED'], 'localrelay': True, 'timeoffset': 0, 'networkactive': True, 'connections': 0, 'networks': [{'name': 'ipv4', 'limited': False, 'reachable': True, 'proxy': '', 'proxy_randomize_credentials': False}, {'name': 'ipv6', 'limited': False, 'reachable': True, 'proxy': '', 'proxy_randomize_credentials': False}, {'name': 'onion', 'limited': True, 'reachable': False, 'proxy': '', 'proxy_randomize_credentials': False}], 'relayfee': 1e-05, 'incrementalfee': 1e-05, 'localaddresses': [{'address': '2a02:810d:d00:7700:233e:a7e:ded8:f2da', 'port': 18542, 'score': 1}, {'address': '2a02:810d:d00:7700:29ec:5c5b:196b:78b2', 'port': 18542, 'score': 1}], 'warnings': ''}
        assert node.network_info["connections"] == 0
        assert node.network_info["warnings"] == ""
        # Testing deleting the wallet file on the node
        with pytest.raises(
            SpecterError,
            match="Trying to delete the wallet file on the node but the wallet had not been unloaded properly.",
        ):
            node.delete_wallet_file(wallet)
        # No error raised now anymore since the wallet was unloaded
        # Should return False because of datadir being "" which translates to the default datadir which the tests are not using.
        node.delete_wallet_file(wallet) == False
        # Update the datadir to the correct one
        node.update_rpc(datadir=bitcoin_regtest.datadir)
        node.delete_wallet_file(wallet) == True


@pytest.mark.elm
def test_Node_elm(elements_elreg):
    with tempfile.TemporaryDirectory("_some_datafolder_tmp") as data_folder:
        node = Node.from_json(
            {
                "autodetect": False,
                "datadir": "",
                "user": elements_elreg.rpcconn.rpcuser,
                "password": elements_elreg.rpcconn.rpcpassword,
                "port": elements_elreg.rpcconn.rpcport,
                "host": elements_elreg.rpcconn.ipaddress,
                "protocol": "http",
            },
            manager=MagicMock(),
            default_fullpath=os.path.join(data_folder, "a_testfile.json"),
        )
        result = node.test_rpc()

        assert result["tests"]["connectable"] == True
        assert result["tests"]["recent_version"] == True
        assert result["tests"]["credentials"] == True
        assert result["tests"]["wallets"] == True

        node_json = node.json
        del node_json["fullpath"]  # This is very different because of the tempfile
        print(f"node.json = {node.json}")
        assert node_json == {
            "name": "",
            "python_class": "cryptoadvance.specter.node.Node",
            "alias": "",
            "autodetect": False,
            "datadir": "",
            "user": "liquid",
            "password": "secret",
            "port": 18643,
            "host": "localhost",
            "protocol": "http",
            "node_type": "BTC",
        }

        rpc = node._get_rpc()
        assert rpc.getblockchaininfo()["chain"] == "elreg"
        node.rename("some_new_name")
        assert node.json["name"] == "some_new_name"
        node.check_info()
        assert node.is_configured == True
        assert node.is_running == True
        assert node.is_testnet == True
        print(f"info = {node.info}")
        # something like:
        # {'chain': 'regtest', 'blocks': 100, 'headers': 100, 'bestblockhash': '5277c27b3b5e8aad8e079a928e4675931ea1638a28c7a33bae4ef26425402259', 'difficulty': 4.656542373906925e-10, 'mediantime': 1622635607, 'verificationprogress': 1, 'initialblockdownload': False, 'chainwork': '00000000000000000000000000000000000000000000000000000000000000ca', 'size_on_disk': 30477, 'pruned': False, 'softforks': {'bip34': {'type': 'buried', 'active': False, 'height': 500}, 'bip66': {'type': 'buried', 'active': False, 'height': 1251}, 'bip65': {'type': 'buried', 'active': False, 'height': 1351}, 'csv': {'type': 'buried', 'active': False, 'height': 432}, 'segwit': {'type': 'buried', 'active': True, 'height': 0}, 'testdummy': {'type': 'bip9', 'bip9': {'status': 'defined', 'start_time': 0, 'timeout': 9223372036854775807, 'since': 0}, 'active': False}}, 'warnings': '', 'mempool_info': {'loaded': True, 'size': 0, 'bytes': 0, 'usage': 0, 'maxmempool': 300000000, 'mempoolminfee': 1e-05, 'minrelaytxfee': 1e-05}, 'uptime': 480, 'blockfilterindex': False, 'utxorescan': None}
        chain = node.info["chain"]
        assert chain == "elreg"
        assert is_liquid(chain) == True

        print(f"network_info = {node.network_info}")
        # something like:
        # {'version': 200100, 'subversion': '/Satoshi:0.20.1/', 'protocolversion': 70015, 'localservices': '0000000000000409', 'localservicesnames': ['NETWORK', 'WITNESS', 'NETWORK_LIMITED'], 'localrelay': True, 'timeoffset': 0, 'networkactive': True, 'connections': 0, 'networks': [{'name': 'ipv4', 'limited': False, 'reachable': True, 'proxy': '', 'proxy_randomize_credentials': False}, {'name': 'ipv6', 'limited': False, 'reachable': True, 'proxy': '', 'proxy_randomize_credentials': False}, {'name': 'onion', 'limited': True, 'reachable': False, 'proxy': '', 'proxy_randomize_credentials': False}], 'relayfee': 1e-05, 'incrementalfee': 1e-05, 'localaddresses': [{'address': '2a02:810d:d00:7700:233e:a7e:ded8:f2da', 'port': 18542, 'score': 1}, {'address': '2a02:810d:d00:7700:29ec:5c5b:196b:78b2', 'port': 18542, 'score': 1}], 'warnings': ''}
        assert node.network_info["connections"] == 0
        assert node.network_info["warnings"] == ""

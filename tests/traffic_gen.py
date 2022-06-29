#!/usr/bin/env python3
""" Tests an import of a wallet with lots of TXs

This sets up a node and funds a default-wallet w0
This wallet will then create lots of TXs to a wallet w1 which got created
and imported a descriptor.

After that, a SpecterWallet with the same descriptor get created + rescan.
At the end the txlist should be very similiar with the TXs of w1.


"""

import logging
import shutil
import sys
from decimal import Decimal, getcontext
from random import random
import time
from unittest.mock import MagicMock
from bitcoin_comp_layer import SpecterAuthServiceProxy, SpecterBitcoinTestFramework
from cryptoadvance.specter.managers.wallet_manager import WalletManager
from cryptoadvance.specter.persistence import delete_file
from cryptoadvance.specter.rpc import BitcoinRPC, autodetect_rpc_confs
from cryptoadvance.specter.wallet import Wallet
from embit.bip32 import NETWORKS, HDKey
from mock import patch
from test_framework.descriptors import descsum_create
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import (
    assert_equal,
    assert_fee_amount,
    assert_greater_than,
    assert_raises_rpc_error,
    count_bytes,
    get_auth_cookie,
    rpc_port,
)


def test_TrafficGen(
    caplog,
    empty_data_folder,
    acc0xprv_hold_accident,
    acc0key_hold_accident,
    rootkey_hold_accident,
):
    # caplog.set_level(logging.DEBUG)
    durations = {}
    # for i in range(1,2,1):
    for i in range(7000, 8000, 1000):
        shutil.rmtree(empty_data_folder)
        tg = TrafficGen()
        tg.number_of_txs = i
        tg.keypoolrefill = i
        tg.rootkey_hold_accident = rootkey_hold_accident
        tg.acc0key_hold_accident = acc0key_hold_accident

        tg.empty_data_folder = empty_data_folder
        durations[i] = tg.main()

    print(f"results: {durations}")
    for key, value in durations.items():
        print(f"run with {key} TXs took {value} seconds, that's {value/key} secs/tx")


class TrafficGen(SpecterBitcoinTestFramework):
    def set_test_params(self):
        """Override test parameters for your individual test.

        This method must be overridden and num_nodes must be explicitly set."""
        # By default every test loads a pre-mined chain of 200 blocks from cache.
        # Set setup_clean_chain to True to skip this and start from the Genesis
        # block.
        self.setup_clean_chain = False
        self.num_nodes = 1

        # self.log.info("I've finished set_test_params")  # Oops! Can't run self.log before run_test()

    def run_test(self):
        self.log.info("Setup wallets...")
        # w0 is a wallet with coinbase rewards
        self.nodes[0].createwallet(self.default_wallet_name)
        w0 = self.nodes[0].get_wallet_rpc(self.default_wallet_name)
        self.generatetoaddress(self.nodes[0], nblocks=110, address=w0.getnewaddress())

        # w1 contains the private keys acc0xprv_hold_accident
        self.nodes[0].createwallet(wallet_name="w1", blank=True, descriptors=True)
        w1 = self.nodes[0].get_wallet_rpc("w1")
        tpriv = self.rootkey_hold_accident.to_base58(
            version=NETWORKS["regtest"]["xprv"]
        )

        result = w1.importdescriptors(
            [
                {
                    "desc": descsum_create("wpkh(" + tpriv + "/84'/1'/0'/0/*)"),
                    "timestamp": "now",
                    "range": [0, 100],
                    "active": True,
                },
                {
                    "desc": descsum_create("wpkh(" + tpriv + "/84'/1'/1'/1/*)"),
                    "timestamp": "now",
                    "range": [0, 100],
                    "active": True,
                    "internal": True,
                },
            ]
        )

        self.log.info(f"result of importdescriptors: {result}")
        zero_address = w1.getnewaddress()
        self.log.info(f"result of addressinfo: {w1.getaddressinfo(zero_address)}")
        w1.keypoolrefill(199)

        # Create some TXs towards w1
        self.log.info(f"blockheight: {self.nodes[0].getblockchaininfo()['blocks']} ")
        self.log.info(f"result of getbalances (before): {w1.getbalances()}")
        for i in range(0, self.number_of_txs):
            w0.sendtoaddress(w1.getnewaddress(), 0.1)
            if i % 10 and random() > 0.8:
                self.generatetoaddress(
                    self.nodes[0], nblocks=1, address=w0.getnewaddress()
                )

        # be sure that all the TXs are in the chain
        self.generatetoaddress(self.nodes[0], nblocks=1, address=w0.getnewaddress())
        self.log.info(f"blockheight: {self.nodes[0].getblockchaininfo()['blocks']} ")
        self.log.info(f"result of getbalances (after): {w1.getbalances()}")

        # Create the specter-wallet
        wm = WalletManager(
            None,
            self.empty_data_folder,
            self.bitcoin_rpc(),
            "regtest",
            None,
            allow_threading=False,
        )
        wallet: Wallet = wm.create_wallet(
            "hold_accident", 1, "wpkh", [self.acc0key_hold_accident], MagicMock()
        )
        hold_accident = self.nodes[0].get_wallet_rpc("specter/hold_accident")
        ha_zero_address = wallet.get_address(0)

        # Be sure that the addresses of w1 and the specter-wallet matches
        assert ha_zero_address == zero_address

        hold_accident.keypoolrefill(self.number_of_txs + 10)
        wallet.update()

        # Do a rescan
        delete_file(wallet._transactions.path)
        # wallet.fetch_transactions()
        # This rpc call does not seem to return a result; use no_wait to ignore timeout errors
        result = wallet.rpc.rescanblockchain(0)
        print(wallet.rpc.getwalletinfo())
        self.log.info(f"Result of rescanblockchain: {result}")

        # both balances are the same
        assert (
            wallet.rpc.getbalances()["mine"]["trusted"]
            == w1.getbalances()["mine"]["trusted"]
        )

        # Check the number of TXs
        txlist = wallet.txlist(validate_merkle_proofs=False)
        print(f"result of hold_accident.getbalances: {hold_accident.getbalances()}")
        if self.keypoolrefill < self.number_of_txs:
            assert len(txlist) == self.keypoolrefill
        else:
            assert len(txlist) == self.number_of_txs


if __name__ == "__main__":
    TrafficGen().main()

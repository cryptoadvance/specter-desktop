from cryptoadvance.specter.txlist import TxItem, TxList
from embit.transaction import Transaction, TransactionInput


# This is from
# {
#   "in_active_chain": true,
#   "txid": "167ffac3e7193bc53f22984126f95cd7dc3dcaa675ef3d177a8426027a62fc7f",
#   "hash": "0b91b7d8d3bae4895b1c9c789bd7ee29a7918f514597f832589ccc4574ae9dc2",
#   "version": 2,
#   "size": 337,
#   "vsize": 146,
#   "weight": 583,
#   "locktime": 478576,
#   "vin": [
#     {
#       "txid": "5715cc1f19a8698f640e07ed41c7e5e91dbfdd04b8a67d6fe7bc16009e889fea",
#       "vout": 0,
#       "scriptSig": {
#         "asm": "",
#         "hex": ""
#       },
#       "txinwitness": [
#         "",
#         "30450221009c28d4da7c691c8de4ebea400d24acca208de2340b02494f3d2784ffc5338b3c02207eb44becc5ff4d81e2f82f87d69c5fba0296e91fa53a1932e5642e6deb658d5001",
#         "304402203fa0ca4a03304d20c800d7f28f01cfeb8ecc6894e431a1dcbc528a303346280502201fffec9ad74a38b77c8792a812d62799e9e2e198607fcc76ad284b751ae9093a01",
#         "522102f8b9bd22a6ad20e4afcf495a311ea9df1b525eda0ec91a8ae0ead0cb41b4c88421032e452e1f7406d185f384d8e5924ad4ad30728275278d48e393030d36bb13decd2103ead2806c00a19b02a17552d2b427c178a2a7cea062e7ed66a0be0b2a35e9259953ae"
#       ],
#       "sequence": 4294967294
#     }
#   ],
#   "vout": [
#     {
#       "value": 0.00008455,
#       "n": 0,
#       "scriptPubKey": {
#         "asm": "0 430da869def092fbd4d93d881531b87aa896edf6",
#         "hex": "0014430da869def092fbd4d93d881531b87aa896edf6",
#         "reqSigs": 1,
#         "type": "witness_v0_keyhash",
#         "addresses": [
#           "bc1qgvx6s6w77zf0h4xe8kyp2vdc025fdm0key5k5s"
#         ]
#       }
#     }
#   ],
#   "hex": "02000000000101ea9f889e0016bce76f7da6b804ddbf1de9e5c741ed070e648f69a8191fcc15570000000000feffffff010721000000000000160014430da869def092fbd4d93d881531b87aa896edf604004830450221009c28d4da7c691c8de4ebea400d24acca208de2340b02494f3d2784ffc5338b3c02207eb44becc5ff4d81e2f82f87d69c5fba0296e91fa53a1932e5642e6deb658d500147304402203fa0ca4a03304d20c800d7f28f01cfeb8ecc6894e431a1dcbc528a303346280502201fffec9ad74a38b77c8792a812d62799e9e2e198607fcc76ad284b751ae9093a0169522102f8b9bd22a6ad20e4afcf495a311ea9df1b525eda0ec91a8ae0ead0cb41b4c88421032e452e1f7406d185f384d8e5924ad4ad30728275278d48e393030d36bb13decd2103ead2806c00a19b02a17552d2b427c178a2a7cea062e7ed66a0be0b2a35e9259953ae704d0700",
#   "blockhash": "0000000000000000000560dadee3915645a134eaaec35bd5a7b8f4df6f6ce16e",
#   "confirmations": 466,
#   "time": 1642182445,
#   "blocktime": 1642182445
# }


def test_understandTransaction():
    mytx = Transaction.from_string(
        "02000000000101ea9f889e0016bce76f7da6b804ddbf1de9e5c741ed070e648f69a8191fcc15570000000000feffffff010721000000000000160014430da869def092fbd4d93d881531b87aa896edf604004830450221009c28d4da7c691c8de4ebea400d24acca208de2340b02494f3d2784ffc5338b3c02207eb44becc5ff4d81e2f82f87d69c5fba0296e91fa53a1932e5642e6deb658d500147304402203fa0ca4a03304d20c800d7f28f01cfeb8ecc6894e431a1dcbc528a303346280502201fffec9ad74a38b77c8792a812d62799e9e2e198607fcc76ad284b751ae9093a0169522102f8b9bd22a6ad20e4afcf495a311ea9df1b525eda0ec91a8ae0ead0cb41b4c88421032e452e1f7406d185f384d8e5924ad4ad30728275278d48e393030d36bb13decd2103ead2806c00a19b02a17552d2b427c178a2a7cea062e7ed66a0be0b2a35e9259953ae704d0700"
    )
    assert mytx.version == 2
    assert mytx.locktime == 478576
    # assert type(mytx.vin) == TransactionInput # ?? AssertionError: assert <class 'list'> == TransactionInput ??


def test_TxItem(empty_data_folder):
    mytxitem = TxItem(
        None,
        [],
        empty_data_folder,
        hex="02000000000101ea9f889e0016bce76f7da6b804ddbf1de9e5c741ed070e648f69a8191fcc15570000000000feffffff010721000000000000160014430da869def092fbd4d93d881531b87aa896edf604004830450221009c28d4da7c691c8de4ebea400d24acca208de2340b02494f3d2784ffc5338b3c02207eb44becc5ff4d81e2f82f87d69c5fba0296e91fa53a1932e5642e6deb658d500147304402203fa0ca4a03304d20c800d7f28f01cfeb8ecc6894e431a1dcbc528a303346280502201fffec9ad74a38b77c8792a812d62799e9e2e198607fcc76ad284b751ae9093a0169522102f8b9bd22a6ad20e4afcf495a311ea9df1b525eda0ec91a8ae0ead0cb41b4c88421032e452e1f7406d185f384d8e5924ad4ad30728275278d48e393030d36bb13decd2103ead2806c00a19b02a17552d2b427c178a2a7cea062e7ed66a0be0b2a35e9259953ae704d0700",
        blocktime=1642182445,  # arbitrary stuff can get passed
    )
    # a TxItem pretty much works like a hash with some extrafunctionality
    assert mytxitem["blocktime"] == 1642182445
    # We can also add data after the fact
    mytxitem["confirmations"] = 123
    assert mytxitem["confirmations"] == 123


def test_txlist(empty_data_folder, bitcoin_regtest):
    mytxlist = TxList(empty_data_folder, None, None)

from binascii import hexlify
from cryptoadvance.specter.txlist import TxItem, TxList
from embit.transaction import Transaction, TransactionInput
import json
from mock import MagicMock

descriptor = "[78738c82/84h/1h/0h]vpub5YN2RvKrA9vGAoAdpsruQGfQMWZzaGt3M5SGMMhW8i2W4SyNSHMoLtyyLLS6EjSzLfrQcbtWdQcwNS6AkCWne1Y7U8bt9JgVYxfeH9mCVPH"
# The example transaction from a regtest
test_tx = json.loads(
    """
{
  "in_active_chain": true,
  "txid": "42f5c9e826e52cde883cde7a6c7b768db302e0b8b32fc52db75ad3c5711b4a9e",
  "hash": "d93c51fe9b7d001a795e98dd1357de42647cda08fe5072703f7e438154402bb6",
  "version": 2,
  "size": 191,
  "vsize": 110,
  "weight": 437,
  "locktime": 415,
  "vin": [
    {
      "txid": "c7c9dd852fa9cbe72b2f6e3b2eeba1a2b47dc4422b3719a55381be8010d7993f",
      "vout": 0,
      "scriptSig": {
        "asm": "",
        "hex": ""
      },
      "txinwitness": [
        "304402201088bfd110dd891b7f16c5d50d10e6f99cf79d48673d890e3563f8275500315b02205a75e89f794a3e681fe6a7622c642323ac3c802b5f60da2547b2589982795a2401",
        "02578993563d2d00cf1047011fe77a07181a1ab0467044d9b12857c3df65653a50"
      ],
      "sequence": 4294967294
    }
  ],
  "vout": [
    {
      "value": 19.99999890,
      "n": 0,
      "scriptPubKey": {
        "asm": "0 84a2f6e50f4a058b33e39d3d4f12d4a13b20334d",
        "hex": "001484a2f6e50f4a058b33e39d3d4f12d4a13b20334d",
        "reqSigs": 1,
        "type": "witness_v0_keyhash",
        "addresses": [
          "bcrt1qsj30deg0fgzckvlrn5757yk55yajqv6dqx0x7u"
        ]
      }
    }
  ],
  "hex": "020000000001013f99d71080be8153a519372b42c47db4a2a1eb2e3b6e2f2be7cba92f85ddc9c70000000000feffffff01929335770000000016001484a2f6e50f4a058b33e39d3d4f12d4a13b20334d0247304402201088bfd110dd891b7f16c5d50d10e6f99cf79d48673d890e3563f8275500315b02205a75e89f794a3e681fe6a7622c642323ac3c802b5f60da2547b2589982795a24012102578993563d2d00cf1047011fe77a07181a1ab0467044d9b12857c3df65653a509f010000",
  "blockhash": "72523c637e0b93505806564495b1acf915a88bacc45f50e35e8a536becd2f914",
  "confirmations": 222,
  "time": 1642494258,
  "blocktime": 1642494258
}
"""
)


def test_understandTransaction():
    mytx = Transaction.from_string(
        "020000000001013f99d71080be8153a519372b42c47db4a2a1eb2e3b6e2f2be7cba92f85ddc9c70000000000feffffff01929335770000000016001484a2f6e50f4a058b33e39d3d4f12d4a13b20334d0247304402201088bfd110dd891b7f16c5d50d10e6f99cf79d48673d890e3563f8275500315b02205a75e89f794a3e681fe6a7622c642323ac3c802b5f60da2547b2589982795a24012102578993563d2d00cf1047011fe77a07181a1ab0467044d9b12857c3df65653a509f010000"
    )
    assert mytx.version == 2
    assert mytx.locktime == 415
    assert type(mytx.vin[0]) == TransactionInput
    assert (
        hexlify(mytx.vin[0].txid)
        == b"c7c9dd852fa9cbe72b2f6e3b2eeba1a2b47dc4422b3719a55381be8010d7993f"
    )
    assert mytx.vout[0].value == 1999999890
    assert (
        hexlify(mytx.txid())
        == b"42f5c9e826e52cde883cde7a6c7b768db302e0b8b32fc52db75ad3c5711b4a9e"
    )


def test_TxItem(empty_data_folder):
    mytxitem = TxItem(
        None,
        [],
        empty_data_folder,
        hex="020000000001013f99d71080be8153a519372b42c47db4a2a1eb2e3b6e2f2be7cba92f85ddc9c70000000000feffffff01929335770000000016001484a2f6e50f4a058b33e39d3d4f12d4a13b20334d0247304402201088bfd110dd891b7f16c5d50d10e6f99cf79d48673d890e3563f8275500315b02205a75e89f794a3e681fe6a7622c642323ac3c802b5f60da2547b2589982795a24012102578993563d2d00cf1047011fe77a07181a1ab0467044d9b12857c3df65653a509f010000",
        blocktime=1642182445,  # arbitrary stuff can get passed
    )
    # a TxItem pretty much works like a hash with some extrafunctionality
    assert mytxitem["blocktime"] == 1642182445
    # We can also add data after the fact
    mytxitem["confirmations"] = 123
    assert mytxitem.tx.vout
    assert mytxitem["confirmations"] == 123


def test_txlist(empty_data_folder, bitcoin_regtest):
    mytxlist = TxList(empty_data_folder, None, MagicMock())
    mytxlist.descriptor
    mytxlist.add({test_tx["txid"]: test_tx})
    # .add will save implicitely.
    # mytxlist.save()

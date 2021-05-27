from embit.transaction import Transaction
from embit.networks import NETWORKS
from hashlib import sha256
import math

TYPES_MAP = {"p2wpkh": "witness_v0_keyhash"}


def decoderawinput(vin):
    result = {
        "txid": vin.txid.hex(),
        "vout": vin.vout,
        "scriptSig": {
            # TODO: asm
            # "asm": "0014c08fd0c4658b89678b9e0726838c2c2c2f41c3df",
            "hex": vin.script_sig.data.hex()
        },
        "sequence": vin.sequence,
    }
    if vin.is_segwit:
        result["txinwitness"] = [item.hex() for item in vin.witness.items]
    return result


def decoderawoutput(vout, chain):
    result = {
        "value": vout.value * 1e-8,
        "scriptPubKey": {
            # TODO: asm
            # "asm": "0 f81b3e69f5cafc2f1e69ed5625d07876e3558e69",
            "hex": vout.script_pubkey.data.hex(),
            # TODO: reqSigs, type, address only if you can
            # "reqSigs": 1,
            # "type": "witness_v0_keyhash",
        },
    }
    try:
        result["address"] = vout.script_pubkey.address(NETWORKS[chain])
    except:
        pass
    return result


def decoderawtransaction(hextx, chain="main"):
    raw = bytes.fromhex(hextx)
    tx = Transaction.parse(raw)
    txhash = sha256(sha256(raw).digest()).digest()[::-1].hex()
    txsize = len(raw)
    if tx.is_segwit:
        # tx size - flag - marker - witness
        non_witness_size = (
            txsize - 2 - sum([len(inp.witness.serialize()) for inp in tx.vin])
        )
        witness_size = txsize - non_witness_size
        weight = non_witness_size * 4 + witness_size
        vsize = math.ceil(weight / 4)
    else:
        vsize = txsize
        weight = txsize * 4
    result = {
        "txid": tx.txid().hex(),
        "hash": txhash,
        "version": tx.version,
        "size": txsize,
        "vsize": vsize,
        "weight": weight,
        "locktime": tx.locktime,
        "vin": [decoderawinput(vin) for vin in tx.vin],
        "vout": [
            dict(decoderawoutput(vout, chain), n=i) for i, vout in enumerate(tx.vout)
        ],
    }
    return result

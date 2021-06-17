"""
    Utility functions for common test suite tasks
"""


def spend_utxo(device, wallet, utxo):
    inputs = [{"txid": utxo["txid"], "vout": utxo["vout"]}]
    outputs = {wallet.getnewaddress(): 0.0001}
    tx = wallet.rpc.createrawtransaction(inputs, outputs)
    txF = wallet.rpc.fundrawtransaction(tx)
    txFS = device.sign_raw_tx(txF["hex"], wallet)
    txid = wallet.rpc.sendrawtransaction(txFS["hex"])

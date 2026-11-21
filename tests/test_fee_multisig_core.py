"""Measure actual signed 2-of-3 descriptor multisig fees with regtest Bitcoin Core.

Unlike an RPC funding stub, these tests exercise Core's real funding estimate,
Specter's createpsbt, two real hot-key signatures and Core finalization.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from fix_devices_and_wallets import create_hot_wallet_device


@pytest.mark.parametrize("kind", ["wsh", "sh-wsh", "sh"])
def test_multisig_real_signed_fee_rate(
    kind, bitcoin_regtest, specter_regtest_configured, hot_wallet_device_1, hot_wallet_device_2
):
    third = create_hot_wallet_device(specter_regtest_configured)
    devices = [hot_wallet_device_1, hot_wallet_device_2, third]
    # The same derived xpubs can be wrapped by each of Core's multisig script
    # types; the two hot devices hold the private keys for the first two.
    keys = [next(key for key in device.keys if key.key_type == "wsh") for device in devices]
    wallet = specter_regtest_configured.wallet_manager.create_wallet(
        "fee_multisig_" + kind.replace("-", "_") + "_" + uuid4().hex[:8],
        2, kind, keys, devices,
    )
    assert wallet.sigs_required == 2
    assert len(wallet.keys) == 3
    assert wallet.descriptor.is_basic_multisig
    bitcoin_regtest.testcoin_faucet(wallet.getnewaddress(), amount=1)
    wallet.update()
    destination = wallet.getnewaddress()
    psbt = wallet.createpsbt([destination], [0.1], fee_rate=10, readonly=True)
    signed = str(psbt)
    for device in devices[:2]:
        response = device.sign_psbt(signed, wallet, "")
        signed = response["psbt"]
    finalized = wallet.rpc.finalizepsbt(signed)
    assert finalized["complete"]
    decoded = wallet.rpc.decoderawtransaction(finalized["hex"])
    actual = Decimal(str(psbt.fee)) / Decimal(decoded["vsize"])
    assert Decimal("10") <= actual <= Decimal("10.1"), (
        f"{kind}: requested 10 sat/vB, paid {actual} sat/vB"
    )

import pytest
import random
import time

from cryptoadvance.specter.util.mnemonic import generate_mnemonic
from cryptoadvance.specter.process_controller.node_controller import NodeController
from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.wallet import Wallet, Device


mnemonic_ghost = (
    "ghost ghost ghost ghost ghost ghost ghost ghost ghost ghost ghost machine"
)
mnemonic_zoo = (
    "zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo when"
)


def create_hot_wallet_device(
    specter_regtest_configured, name=None, mnemonic=None
) -> Device:
    if mnemonic == None:
        mnemonic = generate_mnemonic(strength=128)
    if name == None:
        name = "_".join(mnemonic.split(" ")[0:3])
    wallet_manager = specter_regtest_configured.wallet_manager
    device_manager = specter_regtest_configured.device_manager

    # Create the device
    device = device_manager.add_device(name=name, device_type="bitcoincore", keys=[])
    device.setup_device(file_password=None, wallet_manager=wallet_manager)
    device.add_hot_wallet_keys(
        mnemonic=mnemonic,
        passphrase="",
        paths=[
            "m/49h/1h/0h",  #  Single Sig (Nested)
            "m/84h/1h/0h",  #  Single Sig (Segwit)'
            "m/86h/1h/0h",  # Single Sig (Taproot)    #  Taproot ONLY works if this derivation path is enabled. The wallet descriptor is derived from this
            "m/48h/1h/0h/1h",  # Multisig Sig (Nested)
            "m/48h/1h/0h/2h",  # Multisig Sig (Segwit)
            #                    "m/44h/0h/0h",  # pkh  single-legacy
        ],
        file_password=None,
        wallet_manager=wallet_manager,
        testnet=True,
        keys_range=[0, 1000],
        keys_purposes=[],
    )
    return device


@pytest.fixture
def hot_wallet_device_1(specter_regtest_configured):
    return create_hot_wallet_device(specter_regtest_configured)


@pytest.fixture
def hot_wallet_device_2(specter_regtest_configured):
    return create_hot_wallet_device(specter_regtest_configured)


def create_hot_wallet_with_ID(
    specter_regtest_configured: Specter, hot_wallet_device_1, wallet_id
) -> Wallet:
    device = hot_wallet_device_1
    wallet_manager = specter_regtest_configured.wallet_manager
    assert device.taproot_available(specter_regtest_configured.rpc)

    # create the wallet
    keys = [key for key in device.keys if key.key_type == "wpkh"]
    source_wallet = wallet_manager.create_wallet(wallet_id, 1, "wpkh", keys, [device])
    return source_wallet


@pytest.fixture
def unfunded_hot_wallet_1(specter_regtest_configured, hot_wallet_device_1) -> Wallet:
    return create_hot_wallet_with_ID(
        specter_regtest_configured,
        hot_wallet_device_1,
        f"a_hotwallet_{random.randint(0, 999999)}",
    )


@pytest.fixture
def unfunded_hot_wallet_2(specter_regtest_configured, hot_wallet_device_1) -> Wallet:
    return create_hot_wallet_with_ID(
        specter_regtest_configured,
        hot_wallet_device_1,
        f"a_hotwallet_{random.randint(0, 999999)}",
    )


@pytest.fixture
def funded_hot_wallet_1(
    bitcoin_regtest: NodeController, unfunded_hot_wallet_1: Wallet
) -> Wallet:
    funded_hot_wallet_1 = unfunded_hot_wallet_1
    assert len(funded_hot_wallet_1.txlist()) == 0
    for i in range(0, 10):
        bitcoin_regtest.testcoin_faucet(funded_hot_wallet_1.getnewaddress(), amount=1)
    funded_hot_wallet_1.update()
    for i in range(0, 2):
        bitcoin_regtest.testcoin_faucet(
            funded_hot_wallet_1.getnewaddress(),
            amount=2.5,
            confirm_payment=False,
        )
    time.sleep(0.5)  # needed for tx to propagate
    funded_hot_wallet_1.update()
    # 12 txs
    assert len(funded_hot_wallet_1.txlist()) == 12
    # two of them are unconfirmed
    assert (
        len([tx for tx in funded_hot_wallet_1.txlist() if tx["confirmations"] == 0])
        == 2
    )
    return funded_hot_wallet_1


@pytest.fixture
def funded_hot_wallet_2(
    bitcoin_regtest: NodeController, unfunded_hot_wallet_2: Wallet
) -> Wallet:
    funded_hot_wallet_2 = unfunded_hot_wallet_2
    bitcoin_regtest.testcoin_faucet(funded_hot_wallet_2.getnewaddress())
    return funded_hot_wallet_2

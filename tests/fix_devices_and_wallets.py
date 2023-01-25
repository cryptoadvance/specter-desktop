import pytest
import random
import time

from cryptoadvance.specter.util.mnemonic import generate_mnemonic
from cryptoadvance.specter.process_controller.node_controller import NodeController
from cryptoadvance.specter.managers.wallet_manager import WalletManager
from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.wallet import Wallet, Device


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


@pytest.fixture
def hot_ghost_machine_device(
    specter_regtest_configured: Specter, mnemonic_ghost_machine: str
) -> Device:
    return create_hot_wallet_device(
        specter_regtest_configured,
        name="Ghost machine device",
        mnemonic=mnemonic_ghost_machine,
    )


def create_hot_segwit_wallet(
    specter_regtest_configured: Specter, device: Device, wallet_id
) -> Wallet:
    wallet_manager: WalletManager = specter_regtest_configured.wallet_manager
    assert device.taproot_available(specter_regtest_configured.rpc)

    # create the wallet
    keys = [key for key in device.keys if key.key_type == "wpkh"]
    source_wallet = wallet_manager.create_wallet(wallet_id, 1, "wpkh", keys, [device])
    return source_wallet


def create_hot_taproot_wallet(
    specter_regtest_configured: Specter, device: Device, wallet_id
) -> Wallet:
    wallet_manager = specter_regtest_configured.wallet_manager
    assert device.taproot_available(specter_regtest_configured.rpc)
    keys = [key for key in device.keys if key.key_type == "tr"]
    source_wallet = wallet_manager.create_wallet(wallet_id, 1, "tr", keys, [device])
    return source_wallet


@pytest.fixture
def unfunded_hot_wallet_1(specter_regtest_configured, hot_wallet_device_1) -> Wallet:
    return create_hot_segwit_wallet(
        specter_regtest_configured,
        hot_wallet_device_1,
        f"a_hotwallet_{random.randint(0, 999999)}",
    )


@pytest.fixture
def unfunded_hot_wallet_2(specter_regtest_configured, hot_wallet_device_2) -> Wallet:
    return create_hot_segwit_wallet(
        specter_regtest_configured,
        hot_wallet_device_1,
        f"a_hotwallet_{random.randint(0, 999999)}",
    )


@pytest.fixture
def unfunded_ghost_machine_wallet(
    specter_regtest_configured: Specter, hot_ghost_machine_device: Device
) -> Wallet:
    return create_hot_segwit_wallet(
        specter_regtest_configured,
        hot_ghost_machine_device,
        f"ghost_machine",
    )


@pytest.fixture
def unfunded_taproot_wallet(
    specter_regtest_configured: Specter, hot_ghost_machine_device: Device
) -> Wallet:
    return create_hot_taproot_wallet(
        specter_regtest_configured,
        hot_ghost_machine_device,
        f"taproot",
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
    time.sleep(1)  # needed for tx to propagate
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


@pytest.fixture
def funded_ghost_machine_wallet(
    bitcoin_regtest: NodeController, unfunded_ghost_machine_wallet: Wallet
) -> Wallet:
    funded_ghost_machine_wallet = unfunded_ghost_machine_wallet
    if funded_ghost_machine_wallet.amount_total == 0:
        bitcoin_regtest.testcoin_faucet(
            funded_ghost_machine_wallet.getnewaddress()
        )  # default value are 20 BTC
    return funded_ghost_machine_wallet


@pytest.fixture
def funded_taproot_wallet(
    bitcoin_regtest: NodeController, unfunded_taproot_wallet: Wallet
) -> Wallet:
    funded_taproot_wallet = unfunded_taproot_wallet
    bitcoin_regtest.testcoin_faucet(
        funded_taproot_wallet.getnewaddress()
    )  # default value are 20 BTC
    return funded_taproot_wallet


def create_trezor_wallet_with_account(
    devices_filled_data_folder,
    device_manager,
    node,
    account_number: int,
    checkbalance=True,
):
    """An ordinary wallet without private keys"""
    wm = WalletManager(
        devices_filled_data_folder,
        node._get_rpc(),
        "regtest",
        device_manager,
    )
    device: Device = device_manager.get_by_alias("trezor")
    wallet_name = f"test_wallet_{random.randint(0, 999999)}"
    ss_segwit_index = account_number * 4 + 1
    assert device.keys[ss_segwit_index].derivation.startswith(
        f"m/84h/1h/{account_number}h"
    ), f"At index ss_segwit_index has weird derivation {device.keys[ss_segwit_index].derivation}"
    wm.create_wallet(wallet_name, 1, "wpkh", [device.keys[ss_segwit_index]], [device])
    wallet: Wallet = wm.wallets[wallet_name]
    if checkbalance:
        assert (
            wallet.rpc.getbalance() == 0
        ), f"account {account_number} does have a non-zero balance: {wallet.rpc.getbalance()}"
    return wallet


@pytest.fixture
def trezor_wallet_acc0(devices_filled_data_folder, device_manager, node):
    """This wallet might have a nonzero balance"""
    return create_trezor_wallet_with_account(
        devices_filled_data_folder, device_manager, node, 0, checkbalance=False
    )
    # raise Exception("Do not use this fixture!")


@pytest.fixture
def trezor_wallet_acc1(devices_filled_data_folder, device_manager, node):
    return create_trezor_wallet_with_account(
        devices_filled_data_folder, device_manager, node, 1
    )


@pytest.fixture
def trezor_wallet_acc2(devices_filled_data_folder, device_manager, node):
    return create_trezor_wallet_with_account(
        devices_filled_data_folder, device_manager, node, 2
    )


@pytest.fixture
def trezor_wallet_acc3(devices_filled_data_folder, device_manager, node):
    return create_trezor_wallet_with_account(
        devices_filled_data_folder, device_manager, node, 3
    )


@pytest.fixture
def trezor_wallet_acc4(devices_filled_data_folder, device_manager, node):
    return create_trezor_wallet_with_account(
        devices_filled_data_folder, device_manager, node, 4
    )


@pytest.fixture
def trezor_wallet_acc5(devices_filled_data_folder, device_manager, node):
    return create_trezor_wallet_with_account(
        devices_filled_data_folder, device_manager, node, 5
    )


@pytest.fixture
def trezor_wallet_acc6(devices_filled_data_folder, device_manager, node):
    return create_trezor_wallet_with_account(
        devices_filled_data_folder, device_manager, node, 6
    )


@pytest.fixture
def trezor_wallet_acc7(devices_filled_data_folder, device_manager, node):
    return create_trezor_wallet_with_account(
        devices_filled_data_folder, device_manager, node, 7
    )

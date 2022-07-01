import logging
import os
import pytest
import sys
from flask import Blueprint
from cryptoadvance.specter.server import create_app, init_app
from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.config import TestConfig
from conftest import specter_app_with_config


@pytest.mark.slow
def test_home(caplog, client):
    """The root of the app"""
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.specter")
    login(client, "secret")
    result = client.get("/")
    # By default there is no authentication
    assert result.status_code == 302  # REDIRECT.
    result = client.get("/welcome/about")
    assert b"Welcome to Specter" in result.data
    result = client.get("/devices/new_device_type", follow_redirects=True)
    assert result.status_code == 200  # OK.
    assert b"Add Device" in result.data
    result = client.get("/settings", follow_redirects=True)
    assert result.status_code == 200  # OK.
    assert b"Settings" in result.data
    result = client.get("/wallets/new_wallet", follow_redirects=True)
    assert result.status_code == 200  # OK.
    assert b"Select the type of the wallet" in result.data
    logout(client)

    # Login logout testing
    result = client.get("/auth/login", follow_redirects=False)
    assert result.status_code == 200
    assert b"Password" in result.data
    result = login(client, "secret")
    assert b"Logged in successfully." in result.data
    result = logout(client)
    assert b"You were logged out" in result.data
    result = login(client, "non_valid_password")
    assert b"Invalid username or password" in result.data
    result = login(client, "blub")
    assert b"Invalid username or password" in result.data


@pytest.mark.slow
def test_settings_general(caplog, client):
    login(client, "secret")
    result = client.get("/settings/general", follow_redirects=True)
    assert result.status_code == 200  # OK.
    assert b"Network:" in result.data
    assert b"regtest" in result.data


@pytest.mark.slow
def test_settings_general_restore_wallet(bitcoin_regtest, caplog, client):
    login(client, "secret")
    restore_wallets = open(
        "./tests/controller_testdata/restore_wallets.json", "r"
    ).read()
    restore_devices = open(
        "./tests/controller_testdata/restore_devices.json", "r"
    ).read()
    result = client.get("/settings/general", follow_redirects=True)
    assert b"Load Specter backup:" in result.data
    csrf_token = (
        str(result.data)
        .split('<input type="hidden" class="csrf-token" name="csrf_token" value="')[1]
        .split('"')[0]
    )
    result = client.post(
        "/settings/general",
        data=dict(
            action="restore",
            autohide_sensitive_info_timeout="NEVER",
            autologout_timeout="NEVER",
            explorer="CUSTOM",
            custom_explorer="",
            unit="btc",
            fee_estimator="mempool",
            fee_estimator_custom_url="",
            loglevel="debug",
            restoredevices=restore_devices,
            restorewallets=restore_wallets,
            proxy_url="",
            only_tor="off",
            tor_control_port="",
            csrf_token=csrf_token,
        ),
    )
    assert b"Specter data was successfully loaded from backup" in result.data
    assert b"SimpleMyNiceDevice" in result.data
    # assert b'btc Hot Wallet' in result.data # Not sure why this doesn't work
    assert b"myNiceDevice" in result.data
    assert b"btchot" in result.data


def test_APP_URL_PREFIX(caplog):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.specter")
    myapp = specter_app_with_config(
        config={
            "APP_URL_PREFIX": "/someprefix",
            "SPECTER_URL_PREFIX": "",
            "EXT_URL_PREFIX": "/spc/ext",
            "SPECTER_DATA_FOLDER": os.path.expanduser("~/.specter_testing"),
        }
    )
    client = myapp.test_client()
    login(client, "secret")

    # Specter
    result = client.get("/")
    assert result.status_code == 404  # / --> 404
    result = client.get("/someprefix/")
    assert result.status_code == 302  # REDIRECT.
    result = client.get("/someprefix/welcome")
    assert result.status_code == 308  # REDIRECT.
    result = client.get("/someprefix/welcome/")
    assert result.status_code == 302  # REDIRECT.
    result = client.get("/someprefix/welcome/about")
    assert b"Welcome to Specter" in result.data
    view_function_report(myapp)
    # Extensions
    result = client.get("/someprefix/spc/ext/swan/")
    # The swan extension will automatically redirect to /settings/auth
    assert result.status_code == 302
    assert result.location.endswith("/someprefix/settings/auth")


def test_SPECTER_URL_PREFIX(caplog):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.specter")
    myapp = specter_app_with_config(
        config={
            "SPECTER_API_ACTIVE": True,
            "APP_URL_PREFIX": "",
            "SPECTER_URL_PREFIX": "/someprefix",
            "EXT_URL_PREFIX": "/someprefix/extensions",
            "SPECTER_DATA_FOLDER": os.path.expanduser("~/.specter_testing"),
        }
    )
    client = myapp.test_client()
    login(client, "secret")
    result = client.get("/")
    # The effect is almost the same but you get one more convenient redirect
    assert result.status_code == 302  # REDIRECT.
    result = client.get("/someprefix/")
    assert result.status_code == 302  # REDIRECT.
    result = client.get("/someprefix/welcome")
    assert result.status_code == 308  # REDIRECT.
    result = client.get("/someprefix/welcome/")
    assert result.status_code == 302  # REDIRECT.
    result = client.get("/someprefix/welcome/about")
    assert b"Welcome to Specter" in result.data

    # Extensions
    result = client.get("/someprefix/extensions/swan/")
    view_function_report(myapp)
    # The swan extension will automatically redirect to /settings/auth
    assert result.status_code == 302
    assert result.location.endswith("/someprefix/settings/auth")


def login(client, password):
    """login helper-function"""
    result = client.post(
        "auth/login", data=dict(password=password), follow_redirects=True
    )
    assert (
        b"We could not check your password, maybe Bitcoin Core is not running or not configured?"
        not in result.data
    )
    return result


def logout(client):
    """logout helper-method"""
    return client.get("auth/logout", follow_redirects=True)


def view_function_report(myapp):
    """This might be useful to troubleshoot strange 404 issues which occur from time to time in the tests in this file. This might have multiple possible causes:
       * The hack described in the archblog is not working
       * One of the extensions is not loading properly
       * The api_bp is not loaded due to SPECTER_API_ACTIVE being false
    It's a bit of a disadvantage as you have to add each new endpoint to the list below, though."""
    view_function_list = """api_bp.api
api_bp.resourceliveness
api_bp.resourcepsbt
api_bp.resourcereadyness
api_bp.resourcespecter
api_bp.resourcetxlist
api_bp.resourcewallet
auth_endpoint.login
auth_endpoint.logout
auth_endpoint.register
auth_endpoint.toggle_hide_sensitive_info
devices_endpoint.device
devices_endpoint.device_blinding_key
devices_endpoint.new_device_keys
devices_endpoint.new_device_manual
devices_endpoint.new_device_mnemonic
devices_endpoint.new_device_type
hwi_server.api
hwi_server.hwi_bridge_settings
hwi_server.index
index
liquidissuer_endpoint.api
liquidissuer_endpoint.asset
liquidissuer_endpoint.asset_activities
liquidissuer_endpoint.asset_assignments
liquidissuer_endpoint.asset_distribution
liquidissuer_endpoint.asset_distribution_status
liquidissuer_endpoint.asset_distributions
liquidissuer_endpoint.asset_reissuance
liquidissuer_endpoint.asset_reissuance_status
liquidissuer_endpoint.asset_settings
liquidissuer_endpoint.asset_users
liquidissuer_endpoint.asset_utxos
liquidissuer_endpoint.assets
liquidissuer_endpoint.categories
liquidissuer_endpoint.category
liquidissuer_endpoint.change_assignment
liquidissuer_endpoint.change_distribution
liquidissuer_endpoint.index
liquidissuer_endpoint.managers
liquidissuer_endpoint.new_asset
liquidissuer_endpoint.new_assignment
liquidissuer_endpoint.new_category
liquidissuer_endpoint.new_distribution
liquidissuer_endpoint.new_rawasset
liquidissuer_endpoint.new_user
liquidissuer_endpoint.rawasset
liquidissuer_endpoint.rawassets
liquidissuer_endpoint.settings_get
liquidissuer_endpoint.settings_post
liquidissuer_endpoint.static
liquidissuer_endpoint.treasury
liquidissuer_endpoint.user
liquidissuer_endpoint.users
liveness
nodes_endpoint.internal_node_logs
nodes_endpoint.internal_node_settings
nodes_endpoint.node_settings
nodes_endpoint.switch_node
price_endpoint.toggle
price_endpoint.update
readyness
services_endpoint.associate_addr
services_endpoint.choose
set_language_code
settings_endpoint.assets
settings_endpoint.auth
settings_endpoint.backup_file
settings_endpoint.general
settings_endpoint.get_asset
settings_endpoint.hwi
settings_endpoint.set_asset_label
settings_endpoint.settings
settings_endpoint.tor
setup_endpoint.bitcoind
setup_endpoint.bitcoind_datadir
setup_endpoint.end
setup_endpoint.get_software_setup_status
setup_endpoint.node_type
setup_endpoint.setup_bitcoind
setup_endpoint.setup_bitcoind_datadir
setup_endpoint.setup_tor
setup_endpoint.start
setup_endpoint.tor
setup_endpoint.tor_from_settings
static
swan_endpoint.index
swan_endpoint.integration_check
swan_endpoint.oauth2_auth
swan_endpoint.oauth2_delete_token
swan_endpoint.oauth2_start
swan_endpoint.oauth2_success
swan_endpoint.settings
swan_endpoint.static
swan_endpoint.update_autowithdrawal
swan_endpoint.withdrawals
wallets_endpoint.addresses
wallets_endpoint.failed_wallets
wallets_endpoint.history
wallets_endpoint.import_psbt
wallets_endpoint.new_wallet
wallets_endpoint.new_wallet_type
wallets_endpoint.receive
wallets_endpoint.send
wallets_endpoint.send_new
wallets_endpoint.send_pending
wallets_endpoint.settings
wallets_endpoint.wallet
wallets_endpoint.wallets_overview
wallets_endpoint_api.addresses_list
wallets_endpoint_api.addresses_list_csv
wallets_endpoint_api.addressinfo
wallets_endpoint_api.asset_balances
wallets_endpoint_api.broadcast
wallets_endpoint_api.broadcast_blockexplorer
wallets_endpoint_api.combine
wallets_endpoint_api.decoderawtx
wallets_endpoint_api.estimate_fee
wallets_endpoint_api.fees
wallets_endpoint_api.generatemnemonic
wallets_endpoint_api.get_label
wallets_endpoint_api.get_scantxoutset_status
wallets_endpoint_api.pending_psbt_list
wallets_endpoint_api.rescan_progress
wallets_endpoint_api.set_label
wallets_endpoint_api.tx_history_csv
wallets_endpoint_api.txlist
wallets_endpoint_api.txout_set_info
wallets_endpoint_api.utxo_csv
wallets_endpoint_api.utxo_list
wallets_endpoint_api.wallet_overview_txs_csv
wallets_endpoint_api.wallet_overview_utxo_csv
wallets_endpoint_api.wallets_loading
wallets_endpoint_api.wallets_overview_txlist
wallets_endpoint_api.wallets_overview_utxo_list
welcome_endpoint.about
welcome_endpoint.get_whitepaper
welcome_endpoint.index"""
    assert (
        "\n".join(
            sorted(
                [
                    mytuple[0]
                    for mytuple in myapp.view_functions.items()
                    if mytuple[0] != "index_prefix"
                ]
            )
        )
        == view_function_list
    )
    report = {
        "liquidissuer": 0,
        "swan": 0,
        "hwi": 0,
        "welcome": 0,
        "auth": 0,
        "devices": 0,
        "nodes": 0,
        "price": 0,
        "services": 0,
        "settings": 0,
        "setup": 0,
        "wallets": 0,
        "api": 0,
        "all": 0,
    }
    print("\n".join(sorted([mytuple[0] for mytuple in myapp.view_functions.items()])))
    for func in myapp.view_functions:
        category = func.split("_")[0]
        report["all"] = report["all"] + 1
        try:
            report[category] = report[category] + 1
        except KeyError:
            pass
    for key, value in report.items():
        print("{: <28}:{}".format(key, value))
    assert report["liquidissuer"] >= 33
    assert report["swan"] >= 10
    assert report["hwi"] >= 3
    assert report["welcome"] >= 3
    assert report["auth"] >= 4
    assert report["devices"] >= 6
    assert report["nodes"] >= 4
    assert report["price"] >= 2
    assert report["services"] >= 2
    assert report["settings"] >= 9
    assert report["setup"] >= 11
    assert report["wallets"] >= 39
    assert report["api"] >= 7
    assert report["all"] >= 138

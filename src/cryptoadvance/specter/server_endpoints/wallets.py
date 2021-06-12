import ast
import base64
import csv
import json
import logging
import os
import random
import time
from binascii import b2a_base64
from datetime import datetime
from functools import wraps
from io import StringIO
from math import isnan
from numbers import Number

import requests
from flask import Blueprint, Flask
from flask import current_app as app
from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.wrappers import Response

from ..helpers import (
    bcur2base64,
    get_devices_with_keys_by_type,
    get_txid,
    is_testnet,
    parse_wallet_data_import,
)
from ..key import Key
from ..persistence import delete_file
from ..rpc import RpcError
from ..specter import Specter
from ..specter_error import SpecterError, handle_exception
from ..util.base43 import b43_decode
from ..util.descriptor import AddChecksum, Descriptor
from ..util.fee_estimation import get_fees
from ..util.price_providers import get_price_at
from ..util.tx import decoderawtransaction
from ..managers.wallet_manager import purposes

rand = random.randint(0, 1e32)  # to force style refresh

# Setup endpoint blueprint
wallets_endpoint = Blueprint("wallets_endpoint", __name__)


def handle_wallet_error(func_name, error):
    flash(f"SpecterError while {func_name}: {error}", "error")
    app.logger.error(f"SpecterError while {func_name}: {error}")
    app.specter.wallet_manager.update()
    return redirect(url_for("about"))


def check_wallet(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        """checks the wallet for healthyness A wrapper function"""
        if kwargs["wallet_alias"]:
            wallet_alias = kwargs["wallet_alias"]
            print("--------------------checking wallet")
            wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
            wallet.get_info()
        return func(*args, **kwargs)

    return wrapper


################## Wallet overview #######################


@wallets_endpoint.route("/wallets_overview/")
@login_required
def wallets_overview():
    app.specter.check_blockheight()
    for wallet in list(app.specter.wallet_manager.wallets.values()):
        wallet.get_balance()
        wallet.check_utxo()

    return render_template(
        "wallet/wallets_overview.jinja",
        specter=app.specter,
        rand=rand,
    )


################## Failed wallets fix #######################


@wallets_endpoint.route("/failed_wallets/", methods=["POST"])
@login_required
def failed_wallets():
    if request.method == "POST":
        action = request.form["action"]
        if action == "retry_loading_wallets":
            app.specter.wallet_manager.update()
        elif action == "delete_failed_wallet":
            try:
                wallet = json.loads(request.form["wallet_data"])
                fullpath = wallet["fullpath"]
                delete_file(fullpath)
                delete_file(fullpath + ".bkp")
                delete_file(fullpath.replace(".json", "_addr.csv"))
                delete_file(fullpath.replace(".json", "_txs.csv"))
                app.specter.wallet_manager.update()
            except Exception as e:

                flash(f"Failed to delete failed wallet: {str(e)}", "error")
    return redirect("/")


################## New wallet #######################


@wallets_endpoint.route("/new_wallet/")
@login_required
def new_wallet_type():
    err = None
    if app.specter.chain is None:
        err = "Configure Bitcoin Core to create wallets"
        return render_template("base.jinja", error=err, specter=app.specter, rand=rand)
    try:
        # Make sure wallet is enabled on Bitcoin Core
        app.specter.rpc.listwallets()
    except Exception:
        err = '<p><br>Configure Bitcoin Core is running with wallets disabled.<br><br>Please make sure disablewallet is off (set disablewallet=0 in your bitcoin.conf), then restart Bitcoin Core and try again.<br>See <a href="https://github.com/cryptoadvance/specter-desktop/blob/34ca139694ecafb2e7c2bd5ad5c4ac74c6d11501/docs/faq.md#im-not-sure-i-want-the-bitcoin-core-wallet-functionality-to-be-used-is-that-mandatory-if-so-is-it-considered-secure" target="_blank" style="color: white;">here</a> for more information.</p>'
        return render_template("base.jinja", error=err, specter=app.specter, rand=rand)
    return render_template(
        "wallet/new_wallet/new_wallet_type.jinja", specter=app.specter, rand=rand
    )


@wallets_endpoint.route("/new_wallet/<wallet_type>/", methods=["GET", "POST"])
@login_required
def new_wallet(wallet_type):
    wallet_types = ["simple", "multisig", "import_wallet"]
    if wallet_type not in wallet_types:
        flash("Unknown wallet type requested", "error")
        return redirect(url_for("wallets_endpoint.new_wallet_type"))

    err = None
    if request.method == "POST":
        action = request.form["action"]
        if action == "importwallet":
            try:
                wallet_data = json.loads(
                    request.form["wallet_data"].replace("\\'", "").replace("'", "h")
                )
                (
                    wallet_name,
                    recv_descriptor,
                    cosigners_types,
                ) = parse_wallet_data_import(wallet_data)
            except Exception as e:
                flash(f"Unsupported wallet import format:{e}", "error")
                return redirect(url_for("wallets_endpoint.new_wallet_type"))
            # get min of the two
            # if the node is still syncing
            # and the first block with tx is not there yet
            startblock = min(
                wallet_data.get("blockheight", app.specter.info.get("blocks", 0)),
                app.specter.info.get("blocks", 0),
            )
            # check if pruned
            if app.specter.info.get("pruned", False):
                newstartblock = max(startblock, app.specter.info.get("pruneheight", 0))
                if newstartblock > startblock:
                    flash(
                        f"Using pruned node - we will only rescan from block {newstartblock}",
                        "error",
                    )
                    startblock = newstartblock
            try:
                descriptor = Descriptor.parse(
                    AddChecksum(recv_descriptor.split("#")[0]),
                    testnet=is_testnet(app.specter.chain),
                )
                if descriptor is None:
                    flash("Invalid wallet descriptor.", "error")
                    return redirect(url_for("wallets_endpoint.new_wallet_type"))
            except:
                flash("Invalid wallet descriptor.", "error")
                return redirect(url_for("wallets_endpoint.new_wallet_type"))
            if wallet_name in app.specter.wallet_manager.wallets_names:
                flash("Wallet with the same name already exists", "error")
                return redirect(url_for("wallets_endpoint.new_wallet_type"))

            sigs_total = descriptor.multisig_N
            sigs_required = descriptor.multisig_M
            if descriptor.wpkh:
                address_type = "wpkh"
            elif descriptor.wsh:
                address_type = "wsh"
            elif descriptor.sh_wpkh:
                address_type = "sh-wpkh"
            elif descriptor.sh_wsh:
                address_type = "sh-wsh"
            elif descriptor.sh:
                address_type = "sh-wsh"
            else:
                address_type = "pkh"
            keys = []
            cosigners = []
            unknown_cosigners = []
            unknown_cosigners_types = []
            if sigs_total == None:
                sigs_total = 1
                sigs_required = 1
                descriptor.origin_fingerprint = [descriptor.origin_fingerprint]
                descriptor.origin_path = [descriptor.origin_path]
                descriptor.base_key = [descriptor.base_key]
            for i in range(sigs_total):
                cosigner_found = False
                for device in app.specter.device_manager.devices:
                    cosigner = app.specter.device_manager.devices[device]
                    if descriptor.origin_fingerprint[i] is None:
                        descriptor.origin_fingerprint[i] = ""
                    if descriptor.origin_path[i] is None:
                        descriptor.origin_path[i] = descriptor.origin_fingerprint[i]
                    for key in cosigner.keys:
                        if key.fingerprint + key.derivation.replace(
                            "m", ""
                        ) == descriptor.origin_fingerprint[i] + descriptor.origin_path[
                            i
                        ].replace(
                            "'", "h"
                        ):
                            keys.append(key)
                            cosigners.append(cosigner)
                            cosigner_found = True
                            break
                    if cosigner_found:
                        break
                if not cosigner_found:
                    desc_key = Key.parse_xpub(
                        "[{}{}]{}".format(
                            descriptor.origin_fingerprint[i],
                            descriptor.origin_path[i],
                            descriptor.base_key[i],
                        )
                    )
                    unknown_cosigners.append(desc_key)
                    if len(unknown_cosigners) > len(cosigners_types):
                        unknown_cosigners_types.append("other")
                    else:
                        unknown_cosigners_types.append(cosigners_types[i])
            wallet_type = "multisig" if sigs_total > 1 else "simple"
            createwallet = "createwallet" in request.form
            if createwallet:
                wallet_name = request.form["wallet_name"]
                for i, unknown_cosigner in enumerate(unknown_cosigners):
                    unknown_cosigner_name = request.form[
                        "unknown_cosigner_{}_name".format(i)
                    ]
                    unknown_cosigner_type = request.form.get(
                        "unknown_cosigner_{}_type".format(i), "other"
                    )
                    device = app.specter.device_manager.add_device(
                        name=unknown_cosigner_name,
                        device_type=unknown_cosigner_type,
                        keys=[unknown_cosigner],
                    )
                    keys.append(unknown_cosigner)
                    cosigners.append(device)
                try:
                    wallet = app.specter.wallet_manager.create_wallet(
                        wallet_name, sigs_required, address_type, keys, cosigners
                    )
                except Exception as e:
                    flash("Failed to create wallet: %r" % e, "error")
                    return redirect(url_for("wallets_endpoint.new_wallet_type"))
                wallet.keypoolrefill(0, wallet.IMPORT_KEYPOOL, change=False)
                wallet.keypoolrefill(0, wallet.IMPORT_KEYPOOL, change=True)
                wallet.import_labels(wallet_data.get("labels", {}))
                flash("Wallet imported successfully", "info")
                try:
                    wallet.rpc.rescanblockchain(startblock, timeout=1)
                    app.logger.info("Rescanning Blockchain ...")
                except requests.exceptions.ReadTimeout:
                    # this is normal behavior in our usecase
                    pass
                except Exception as e:
                    app.logger.error("Exception while rescanning blockchain: %r" % e)
                    flash("Failed to perform rescan for wallet: %r" % e, "error")
                wallet.getdata()
                return redirect(
                    url_for("wallets_endpoint.receive", wallet_alias=wallet.alias)
                    + "?newwallet=true"
                )
            else:
                return render_template(
                    "wallet/new_wallet/import_wallet.jinja",
                    wallet_data=json.dumps(wallet_data),
                    wallet_type=wallet_type,
                    wallet_name=wallet_name,
                    cosigners=cosigners,
                    unknown_cosigners=unknown_cosigners,
                    unknown_cosigners_types=unknown_cosigners_types,
                    sigs_required=sigs_required,
                    sigs_total=sigs_total,
                    specter=app.specter,
                    rand=rand,
                )
        if action == "device":
            cosigners = [
                app.specter.device_manager.get_by_alias(alias)
                for alias in request.form.getlist("devices")
            ]

            if not cosigners:
                return render_template(
                    "wallet/new_wallet/new_wallet.jinja",
                    wallet_type=wallet_type,
                    error="No device was selected. Please select a device to create the wallet for.",
                    specter=app.specter,
                    rand=rand,
                )
            devices = get_devices_with_keys_by_type(app, cosigners, wallet_type)
            for device in devices:
                if len(device.keys) == 0:
                    err = (
                        "Device %s doesn't have keys matching this wallet type"
                        % device.name
                    )
                    break

            name = wallet_type.title()
            wallet_name = name
            i = 2
            while wallet_name in app.specter.wallet_manager.wallets_names:
                wallet_name = "%s %d" % (name, i)
                i += 1

            return render_template(
                "wallet/new_wallet/new_wallet_keys.jinja",
                cosigners=devices,
                wallet_type=wallet_type,
                sigs_total=len(devices),
                sigs_required=max(len(devices) * 2 // 3, 1),
                error=err,
                specter=app.specter,
                rand=rand,
            )
        if action == "key" and err is None:
            wallet_name = request.form["wallet_name"]
            address_type = request.form["type"]
            sigs_total = int(request.form.get("sigs_total", 1))
            sigs_required = int(request.form.get("sigs_required", 1))
            if wallet_name in app.specter.wallet_manager.wallets_names:
                err = "Wallet already exists"
            if err:
                devices = [
                    app.specter.device_manager.get_by_alias(
                        request.form.get("cosigner{}".format(i))
                    )
                    for i in range(0, sigs_total)
                ]
                return render_template(
                    "wallet/new_wallet/new_wallet_keys.jinja",
                    cosigners=devices,
                    wallet_type=wallet_type,
                    sigs_total=len(devices),
                    sigs_required=max(len(devices) * 2 // 3, 1),
                    error=err,
                    specter=app.specter,
                    rand=rand,
                )

            keys = []
            cosigners = []
            devices = []
            for i in range(sigs_total):
                try:
                    key = request.form["key%d" % i]
                    cosigner_name = request.form["cosigner%d" % i]
                    cosigner = app.specter.device_manager.get_by_alias(cosigner_name)
                    cosigners.append(cosigner)
                    for k in cosigner.keys:
                        if k.original == key:
                            keys.append(k)
                            break
                except:
                    pass
            if len(keys) != sigs_total or len(cosigners) != sigs_total:
                err = "No keys were selected for device, please try adding keys first"
                devices = [
                    app.specter.device_manager.get_by_alias(
                        request.form.get("cosigner{}".format(i))
                    )
                    for i in range(0, sigs_total)
                ]
                return render_template(
                    "wallet/new_wallet/new_wallet_keys.jinja",
                    cosigners=devices,
                    wallet_type=wallet_type,
                    sigs_total=len(devices),
                    sigs_required=max(len(devices) * 2 // 3, 1),
                    error=err,
                    specter=app.specter,
                    rand=rand,
                )

            # create a wallet here
            try:
                wallet = app.specter.wallet_manager.create_wallet(
                    wallet_name, sigs_required, address_type, keys, cosigners
                )
            except Exception as e:
                err = f"Failed to create wallet. Error: {e}"
                return render_template(
                    "wallet/new_wallet/new_wallet_keys.jinja",
                    cosigners=cosigners,
                    wallet_type=wallet_type,
                    sigs_total=len(devices),
                    sigs_required=max(len(devices) * 2 // 3, 1),
                    error=err,
                    specter=app.specter,
                    rand=rand,
                )

            app.logger.info("Created Wallet %s" % wallet_name)
            rescan_blockchain = "rescanblockchain" in request.form
            if rescan_blockchain:
                # old wallet - import more addresses
                wallet.keypoolrefill(0, wallet.IMPORT_KEYPOOL, change=False)
                wallet.keypoolrefill(0, wallet.IMPORT_KEYPOOL, change=True)
                if "utxo" in request.form.get("full_rescan_option"):
                    explorer = None
                    if "use_explorer" in request.form:
                        if request.form["explorer"] == "CUSTOM":
                            explorer = request.form["custom_explorer"]
                        else:
                            explorer = app.config["EXPLORERS_LIST"][
                                request.form["explorer"]
                            ]["url"]
                    wallet.rescanutxo(
                        explorer,
                        app.specter.requests_session(explorer),
                        app.specter.only_tor,
                    )
                    app.specter.info["utxorescan"] = 1
                    app.specter.utxorescanwallet = wallet.alias
                else:
                    app.logger.info("Rescanning Blockchain ...")
                    startblock = int(request.form["startblock"])
                    try:
                        wallet.rpc.rescanblockchain(startblock, timeout=1)
                    except requests.exceptions.ReadTimeout:
                        # this is normal behavior in our usecase
                        pass
                    except Exception as e:
                        app.logger.error(
                            "Exception while rescanning blockchain: %e" % e
                        )
                        err = "%r" % e
                    wallet.getdata()
            return redirect(
                url_for("wallets_endpoint.receive", wallet_alias=wallet.alias)
                + "?newwallet=true"
            )
        if action == "preselected_device":
            return render_template(
                "wallet/new_wallet/new_wallet_keys.jinja",
                cosigners=[
                    app.specter.device_manager.get_by_alias(request.form["device"])
                ],
                wallet_type="simple",
                sigs_total=1,
                sigs_required=1,
                error=err,
                specter=app.specter,
                rand=rand,
            )

    return render_template(
        "wallet/new_wallet/new_wallet.jinja",
        wallet_type=wallet_type,
        error=err,
        specter=app.specter,
        rand=rand,
    )


################## Wallet pages #######################

###### Wallet index page ######
@wallets_endpoint.route("/wallet/<wallet_alias>/")
@login_required
def wallet(wallet_alias):
    wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    if wallet.fullbalance > 0:
        return redirect(url_for("wallets_endpoint.history", wallet_alias=wallet_alias))
    else:
        return redirect(url_for("wallets_endpoint.receive", wallet_alias=wallet_alias))


###### Wallet transaction history ######
@wallets_endpoint.route("/wallet/<wallet_alias>/history/", methods=["GET", "POST"])
@login_required
def history(wallet_alias):
    wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    tx_list_type = "txlist"

    if request.method == "POST":
        action = request.form["action"]
        if action == "freezeutxo":
            wallet.toggle_freeze_utxo(request.form.getlist("selected_utxo"))
            tx_list_type = "utxo"
        elif action == "abandon_tx":
            txid = request.form["txid"]
            try:
                wallet.abandontransaction(txid)
            except SpecterError as e:
                flash(str(e), "error")

    # update balances in the wallet
    app.specter.check_blockheight()
    wallet.get_balance()
    wallet.check_utxo()

    return render_template(
        "wallet/history/wallet_history.jinja",
        wallet_alias=wallet_alias,
        wallet=wallet,
        tx_list_type=tx_list_type,
        specter=app.specter,
        rand=rand,
    )


###### Wallet receive ######


@wallets_endpoint.route("/wallet/<wallet_alias>/receive/", methods=["GET", "POST"])
@login_required
@check_wallet
def receive(wallet_alias):
    wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    if request.method == "POST":
        action = request.form["action"]
        if action == "newaddress":
            wallet.getnewaddress()
        elif action == "updatelabel":
            label = request.form["label"]
            wallet.setlabel(wallet.address, label)
    # check that current address is unused
    # and generate new one if it is
    wallet.check_unused()
    return render_template(
        "wallet/receive/wallet_receive.jinja",
        wallet_alias=wallet_alias,
        wallet=wallet,
        specter=app.specter,
        rand=rand,
    )


###### Wallet send ######


@wallets_endpoint.route("/wallet/<wallet_alias>/send")
@login_required
def send(wallet_alias):
    wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    if len(wallet.pending_psbts) > 0:
        return redirect(
            url_for("wallets_endpoint.send_pending", wallet_alias=wallet_alias)
        )
    else:
        return redirect(url_for("wallets_endpoint.send_new", wallet_alias=wallet_alias))


@wallets_endpoint.route("/wallet/<wallet_alias>/send/new", methods=["GET", "POST"])
@login_required
def send_new(wallet_alias):
    wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    # update balances in the wallet
    wallet.get_balance()
    # update utxo list for coin selection
    wallet.check_utxo()
    psbt = None
    addresses = [""]
    labels = [""]
    amounts = [0]
    amount_units = ["btc"]
    err = None
    ui_option = "ui"
    recipients_txt = ""
    subtract = False
    subtract_from = 1
    fee_options = "dynamic"
    rbf = True
    rbf_utxo = []
    rbf_tx_id = ""
    selected_coins = request.form.getlist("coinselect")
    fee_estimation_data = get_fees(app.specter, app.config)
    if fee_estimation_data.get("failed", None):
        flash("Failed to fetch fee estimations, please use the manual fee calculation")

    fee_rate = fee_estimation_data["hourFee"]

    if request.method == "POST":
        action = request.form.get("action")
        rbf_tx_id = request.form.get("rbf_tx_id", "")
        if action == "createpsbt":
            i = 0
            addresses = []
            labels = []
            amounts = []
            amount_units = []
            ui_option = request.form.get("ui_option", "ui")
            if "ui" in ui_option:
                while "address_{}".format(i) in request.form:
                    addresses.append(request.form["address_{}".format(i)])
                    amount = 0.0
                    try:
                        amount = float(request.form["btc_amount_{}".format(i)])
                    except ValueError:
                        pass
                    if isnan(amount):
                        amount = 0.0
                    amounts.append(amount)
                    amount_units.append(request.form["amount_unit_{}".format(i)])
                    labels.append(request.form["label_{}".format(i)])
                    if request.form["label_{}".format(i)] != "":
                        wallet.setlabel(addresses[i], labels[i])
                    i += 1
            else:
                recipients_txt = request.form["recipients"]
                for output in recipients_txt.splitlines():
                    addresses.append(output.split(",")[0].strip())
                    if request.form.get("amount_unit_text") == "sat":
                        amounts.append(float(output.split(",")[1].strip()) / 1e8)
                    else:
                        amounts.append(float(output.split(",")[1].strip()))
                    labels.append("")
            addresses = [
                address.lower()
                if address.startswith(("BC1", "TB1", "BCRT1"))
                else address
                for address in addresses
            ]
            subtract = bool(request.form.get("subtract", False))
            subtract_from = int(request.form.get("subtract_from", 1))
            fee_options = request.form.get("fee_options")
            if fee_options:
                if "dynamic" in fee_options:
                    fee_rate = float(request.form.get("fee_rate_dynamic"))
                else:
                    if request.form.get("fee_rate"):
                        fee_rate = float(request.form.get("fee_rate"))
            rbf = bool(request.form.get("rbf", False))
            selected_coins = request.form.getlist("coinselect")
            app.logger.info("selected coins: {}".format(selected_coins))
            try:
                psbt = wallet.createpsbt(
                    addresses,
                    amounts,
                    subtract=subtract,
                    subtract_from=subtract_from - 1,
                    fee_rate=fee_rate,
                    rbf=rbf,
                    selected_coins=selected_coins,
                    readonly="estimate_fee" in request.form,
                    rbf_edit_mode=(rbf_tx_id != ""),
                )
                if psbt is None:
                    err = "Probably you don't have enough funds, or something else..."
                else:
                    # calculate new amount if we need to subtract
                    if subtract:
                        for v in psbt["tx"]["vout"]:
                            if addresses[0] in v["scriptPubKey"].get(
                                "addresses", [""]
                            ) or addresses[0] == v["scriptPubKey"].get("address", ""):
                                amounts[0] = v["value"]
            except Exception as e:
                err = e
                app.logger.error(e)
            if err is None:
                if "estimate_fee" in request.form:
                    return jsonify(success=True, psbt=psbt)
                return render_template(
                    "wallet/send/sign/wallet_send_sign_psbt.jinja",
                    psbt=psbt,
                    labels=labels,
                    wallet_alias=wallet_alias,
                    wallet=wallet,
                    specter=app.specter,
                    rand=rand,
                )
            else:
                if "estimate_fee" in request.form:
                    return jsonify(success=False, error=str(err))
        elif action == "rbf":
            try:
                rbf_tx_id = request.form["rbf_tx_id"]
                rbf_fee_rate = float(request.form["rbf_fee_rate"])
                psbt = wallet.bumpfee(rbf_tx_id, rbf_fee_rate)
                return render_template(
                    "wallet/send/sign/wallet_send_sign_psbt.jinja",
                    psbt=psbt,
                    labels=[],
                    wallet_alias=wallet_alias,
                    wallet=wallet,
                    specter=app.specter,
                    rand=rand,
                )
            except Exception as e:
                flash("Failed to perform RBF. Error: %s" % e, "error")
        elif action == "rbf_cancel":
            try:
                rbf_tx_id = request.form["rbf_tx_id"]
                rbf_fee_rate = float(request.form["rbf_fee_rate"])
                psbt = wallet.canceltx(rbf_tx_id, rbf_fee_rate)
                return render_template(
                    "wallet/send/sign/wallet_send_sign_psbt.jinja",
                    psbt=psbt,
                    labels=[],
                    wallet_alias=wallet_alias,
                    wallet=wallet,
                    specter=app.specter,
                    rand=rand,
                )
            except Exception as e:
                flash("Failed to cancel transaction with RBF. Error: %s" % e, "error")
        elif action == "rbf_edit":
            try:
                decoded_tx = wallet.decode_tx(rbf_tx_id)
                addresses = decoded_tx["addresses"]
                amounts = decoded_tx["amounts"]
                selected_coins = [
                    f"{utxo['txid']}, {utxo['vout']}"
                    for utxo in decoded_tx["used_utxo"]
                ]
                fee_rate = float(request.form["rbf_fee_rate"])
                fee_options = "manual"
                rbf = True
            except Exception as e:
                flash("Failed to perform RBF. Error: %s" % e, "error")
        elif action == "signhotwallet":
            passphrase = request.form["passphrase"]
            psbt = json.loads(request.form["psbt"])
            b64psbt = wallet.pending_psbts[psbt["tx"]["txid"]]["base64"]
            device = request.form["device"]
            if "devices_signed" not in psbt or device not in psbt["devices_signed"]:
                try:
                    # get device and sign with it
                    signed_psbt = app.specter.device_manager.get_by_alias(
                        device
                    ).sign_psbt(b64psbt, wallet, passphrase)
                    if signed_psbt["complete"]:
                        if "devices_signed" not in psbt:
                            psbt["devices_signed"] = []
                        psbt["devices_signed"].append(device)
                        psbt["sigs_count"] = len(psbt["devices_signed"])
                        raw = wallet.rpc.finalizepsbt(b64psbt)
                        if "hex" in raw:
                            psbt["raw"] = raw["hex"]
                    signed_psbt = signed_psbt["psbt"]
                except Exception as e:
                    signed_psbt = None
                    flash("Failed to sign PSBT: %s" % e, "error")
            else:
                signed_psbt = None
                flash("Device already signed the PSBT", "error")
            return render_template(
                "wallet/send/sign/wallet_send_sign_psbt.jinja",
                signed_psbt=signed_psbt,
                psbt=psbt,
                labels=labels,
                wallet_alias=wallet_alias,
                wallet=wallet,
                specter=app.specter,
                rand=rand,
            )

    if rbf_tx_id:
        try:
            rbf_utxo = wallet.get_rbf_utxo(rbf_tx_id)
        except Exception as e:
            flash("Failed to get RBF coins. Error: %s" % e, "error")

    show_advanced_settings = (
        ui_option != "ui"
        or subtract
        or fee_options != "dynamic"
        or fee_estimation_data["hourFee"] != fee_rate
        or not rbf
        or selected_coins
    )

    return render_template(
        "wallet/send/new/wallet_send.jinja",
        psbt=psbt,
        ui_option=ui_option,
        recipients_txt=recipients_txt,
        recipients=list(zip(addresses, amounts, amount_units, labels)),
        subtract=subtract,
        subtract_from=subtract_from,
        fee_options=fee_options,
        fee_rate=fee_rate,
        rbf=rbf,
        selected_coins=selected_coins,
        show_advanced_settings=show_advanced_settings,
        rbf_utxo=rbf_utxo,
        rbf_tx_id=rbf_tx_id,
        fee_estimation=fee_rate,
        fee_estimation_data=fee_estimation_data,
        wallet_alias=wallet_alias,
        wallet=wallet,
        specter=app.specter,
        rand=rand,
        error=err,
    )


@wallets_endpoint.route("/wallet/<wallet_alias>/send/pending/", methods=["GET", "POST"])
@login_required
def send_pending(wallet_alias):
    wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    if request.method == "POST":
        action = request.form["action"]
        if action == "deletepsbt":
            try:
                wallet.delete_pending_psbt(
                    json.loads(request.form["pending_psbt"])["tx"]["txid"]
                )
            except Exception as e:
                app.logger.error("Could not delete Pending PSBT: %s" % e)
                flash("Could not delete Pending PSBT!", "error")
        elif action == "openpsbt":
            psbt = json.loads(request.form["pending_psbt"])
            return render_template(
                "wallet/send/sign/wallet_send_sign_psbt.jinja",
                psbt=psbt,
                wallet_alias=wallet_alias,
                wallet=wallet,
                specter=app.specter,
                rand=rand,
            )
    pending_psbts = wallet.pending_psbts
    ######## Migration to multiple recipients format ###############
    for psbt in pending_psbts:
        if not isinstance(pending_psbts[psbt]["address"], list):
            pending_psbts[psbt]["address"] = [pending_psbts[psbt]["address"]]
            pending_psbts[psbt]["amount"] = [pending_psbts[psbt]["amount"]]
    ###############################################################
    return render_template(
        "wallet/send/pending/wallet_sendpending.jinja",
        pending_psbts=pending_psbts,
        wallet_alias=wallet_alias,
        wallet=wallet,
        specter=app.specter,
    )


@wallets_endpoint.route("/wallet/<wallet_alias>/send/import", methods=["GET", "POST"])
@login_required
def import_psbt(wallet_alias):
    wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    if request.method == "POST":
        action = request.form["action"]
        if action == "importpsbt":
            try:
                b64psbt = "".join(request.form["rawpsbt"].split())
                psbt = wallet.importpsbt(b64psbt)
            except Exception as e:
                flash("Could not import PSBT: %s" % e, "error")
                return redirect(
                    url_for("wallets_endpoint.import_psbt", wallet_alias=wallet_alias)
                )
            return render_template(
                "wallet/send/sign/wallet_send_sign_psbt.jinja",
                psbt=psbt,
                wallet_alias=wallet_alias,
                wallet=wallet,
                specter=app.specter,
                rand=rand,
            )
    err = None
    return render_template(
        "wallet/send/import/wallet_importpsbt.jinja",
        wallet_alias=wallet_alias,
        wallet=wallet,
        specter=app.specter,
        rand=rand,
        error=err,
    )


###### Wallet addresses ######


@wallets_endpoint.route("/wallet/<wallet_alias>/addresses/", methods=["GET"])
@login_required
def addresses(wallet_alias):
    """Show informations about cached addresses (wallet._addresses) of the <wallet_alias>.
    It updates balances in the wallet before renderization in order to show updated UTXO and
    balance of each address."""
    wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)

    # update balances in the wallet
    app.specter.check_blockheight()
    wallet.get_balance()
    wallet.check_utxo()

    return render_template(
        "wallet/addresses/wallet_addresses.jinja",
        wallet_alias=wallet_alias,
        wallet=wallet,
        specter=app.specter,
        rand=rand,
    )


###### Wallet settings ######


@wallets_endpoint.route("/wallet/<wallet_alias>/settings/", methods=["GET", "POST"])
@login_required
def settings(wallet_alias):
    wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    error = None
    if request.method == "POST":
        action = request.form["action"]
        if action == "rescanblockchain":
            startblock = int(request.form["startblock"])
            try:
                delete_file(wallet._transactions.path)
                wallet.fetch_transactions()
                res = wallet.rpc.rescanblockchain(startblock, timeout=1)
            except requests.exceptions.ReadTimeout:
                # this is normal behaviour in our usecase
                pass
            except Exception as e:
                app.logger.error("%s while rescanblockchain" % e)
                error = "%r" % e
            wallet.getdata()
        elif action == "abortrescan":
            res = wallet.rpc.abortrescan()
            if not res:
                error = "Failed to abort rescan. Maybe already complete?"
            wallet.getdata()
        elif action == "rescanutxo":
            explorer = None
            if "use_explorer" in request.form:
                if request.form["explorer"] == "CUSTOM":
                    explorer = request.form["custom_explorer"]
                else:
                    explorer = app.config["EXPLORERS_LIST"][request.form["explorer"]][
                        "url"
                    ]

            wallet.rescanutxo(
                explorer, app.specter.requests_session(explorer), app.specter.only_tor
            )
            app.specter.info["utxorescan"] = 1
            app.specter.utxorescanwallet = wallet.alias
        elif action == "abortrescanutxo":
            app.specter.abortrescanutxo()
            app.specter.info["utxorescan"] = None
            app.specter.utxorescanwallet = None
        elif action == "keypoolrefill":
            delta = int(request.form["keypooladd"])
            wallet.keypoolrefill(wallet.keypool, wallet.keypool + delta)
            wallet.keypoolrefill(
                wallet.change_keypool, wallet.change_keypool + delta, change=True
            )
            wallet.getdata()
        elif action == "deletewallet":
            app.specter.wallet_manager.delete_wallet(
                wallet, app.specter.bitcoin_datadir, app.specter.chain
            )
            response = redirect(url_for("index"))
            return response
        elif action == "rename":
            wallet_name = request.form["newtitle"]
            if not wallet_name:
                flash("Wallet name cannot be empty", "error")
            elif wallet_name == wallet.name:
                pass
            elif wallet_name in app.specter.wallet_manager.wallets_names:
                flash("Wallet already exists", "error")
            else:
                app.specter.wallet_manager.rename_wallet(wallet, wallet_name)

    return render_template(
        "wallet/settings/wallet_settings.jinja",
        purposes=purposes,
        wallet_alias=wallet_alias,
        wallet=wallet,
        specter=app.specter,
        rand=rand,
        error=error,
    )


################## Wallet util endpoints #######################
# TODO: move these to an API endpoint


@wallets_endpoint.route("/wallet/<wallet_alias>/combine/", methods=["POST"])
@login_required
def combine(wallet_alias):
    wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    # only post requests
    # FIXME: ugly...
    txid = request.form.get("txid")
    psbts = [request.form.get("psbt0").strip(), request.form.get("psbt1").strip()]
    raw = {}
    combined = None

    for i, psbt in enumerate(psbts):
        if not psbt:
            return "Cannot parse empty data as PSBT", 500
        if "UR:BYTES/" in psbt.upper():
            psbt = bcur2base64(psbt).decode()

        # if electrum then it's base43
        try:
            decoded = b43_decode(psbt)
            if decoded[:5] in [b"psbt\xff", b"pset\xff"]:
                psbt = b2a_base64(decoded).decode()
            else:
                psbt = decoded.hex()
        except:
            pass

        psbts[i] = psbt
        # psbt should start with cHNi
        # if not - maybe finalized hex tx
        if not psbt.startswith("cHNi") and not psbt.startswith("cHNl"):
            raw["hex"] = psbt
            combined = psbts[1 - i]
            # check it's hex
            try:
                bytes.fromhex(psbt)
            except:
                return "Invalid transaction format", 500

    try:
        if "hex" in raw:
            raw["complete"] = True
            raw["psbt"] = combined
        else:
            combined = app.specter.combine(psbts)
            raw = app.specter.finalize(combined)
            if "psbt" not in raw:
                raw["psbt"] = combined
        psbt = wallet.update_pending_psbt(combined, txid, raw)
        raw["devices"] = psbt["devices_signed"]
    except RpcError as e:
        return e.error_msg, e.status_code
    except Exception as e:
        return "Unknown error: %r" % e, 500
    return json.dumps(raw)


@wallets_endpoint.route("/wallet/<wallet_alias>/broadcast/", methods=["GET", "POST"])
@login_required
def broadcast(wallet_alias):
    wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    if request.method == "POST":
        tx = request.form.get("tx")
        res = wallet.rpc.testmempoolaccept([tx])[0]
        if res["allowed"]:
            app.specter.broadcast(tx)
            wallet.delete_pending_psbt(get_txid(tx))
            return jsonify(success=True)
        else:
            return jsonify(
                success=False,
                error="Failed to broadcast transaction: transaction is invalid\n%s"
                % res["reject-reason"],
            )
    return jsonify(success=False, error="broadcast tx request must use POST")


@wallets_endpoint.route(
    "/wallet/<wallet_alias>/broadcast_blockexplorer/", methods=["GET", "POST"]
)
@login_required
def broadcast_blockexplorer(wallet_alias):
    wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    if request.method == "POST":
        tx = request.form.get("tx")
        explorer = request.form.get("explorer")
        use_tor = request.form.get("use_tor", "true") == "true"
        res = wallet.rpc.testmempoolaccept([tx])[0]
        if res["allowed"]:
            try:
                if app.specter.chain == "main":
                    url_network = ""
                elif app.specter.chain == "liquidv1":
                    url_network = "liquid/"
                elif app.specter.chain == "test" or app.specter.chain == "testnet":
                    url_network = "testnet/"
                elif app.specter.chain == "signet":
                    url_network = "signet/"
                else:
                    return jsonify(
                        success=False,
                        error=f"Failed to broadcast transaction. Network not supported.",
                    )
                if explorer == "mempool":
                    explorer = f"MEMPOOL_SPACE{'_ONION' if use_tor else ''}"
                elif explorer == "blockstream":
                    explorer = f"BLOCKSTREAM_INFO{'_ONION' if use_tor else ''}"
                else:
                    return jsonify(
                        success=False,
                        error=f"Failed to broadcast transaction. Block explorer not supported.",
                    )
                requests_session = app.specter.requests_session(force_tor=use_tor)
                requests_session.post(
                    f"{app.config['EXPLORERS_LIST'][explorer]['url']}{url_network}api/tx",
                    data=tx,
                )
                wallet.delete_pending_psbt(get_txid(tx))
                return jsonify(success=True)
            except Exception as e:
                return jsonify(
                    success=False,
                    error=f"Failed to broadcast transaction with error: {e}",
                )
        else:
            return jsonify(
                success=False,
                error="Failed to broadcast transaction: transaction is invalid\n%s"
                % res["reject-reason"],
            )
    return jsonify(success=False, error="broadcast tx request must use POST")


@wallets_endpoint.route("/wallet/<wallet_alias>/decoderawtx/", methods=["GET", "POST"])
@login_required
@app.csrf.exempt
def decoderawtx(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
        txid = request.form.get("txid", "")
        if txid:
            tx = wallet.rpc.gettransaction(txid)
            # This is a fix for Bitcoin Core versions < v0.20
            # These do not return the blockheight as part of the `gettransaction` command
            # So here we check if this property is lacking and if so
            # query the blockheader based on the transaction blockhash
            ##################### Remove from here after dropping Core v0.19 support #####################
            if "blockhash" in tx and "blockheight" not in tx:
                tx["blockheight"] = wallet.rpc.getblockheader(tx["blockhash"])["height"]
            ##################### Remove until here after dropping Core v0.19 support #####################

            if tx["confirmations"] == 0:
                tx["is_purged"] = wallet.is_tx_purged(txid)
                try:
                    if (
                        wallet.gettransaction(txid, decode=True).get("category", "")
                        == "receive"
                    ):
                        tx["fee"] = (
                            wallet.rpc.getmempoolentry(txid)["fees"]["modified"] * -1
                        )
                except Exception as e:
                    handle_exception(e)
                    app.logger.warning(
                        f"Failed to get fees from mempool entry for transaction: {txid}. Error: {e}"
                    )

            try:
                rawtx = decoderawtransaction(tx["hex"], app.specter.chain)
            except:
                rawtx = wallet.rpc.decoderawtransaction(tx["hex"])

            return {
                "success": True,
                "tx": tx,
                "rawtx": rawtx,
                "walletName": wallet.name,
            }
    except Exception as e:
        app.logger.warning("Failed to fetch transaction data. Exception: {}".format(e))
    return {"success": False}


@wallets_endpoint.route(
    "/wallet/<wallet_alias>/rescan_progress", methods=["GET", "POST"]
)
@login_required
@app.csrf.exempt
def rescan_progress(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
        wallet.get_info()
        return {
            "active": wallet.rescan_progress is not None,
            "progress": wallet.rescan_progress,
        }
    except SpecterError as se:
        app.logger.error("SpecterError while get wallet rescan_progress: %s" % se)
        return {}


@wallets_endpoint.route("/wallet/<wallet_alias>/get_label", methods=["POST"])
@login_required
def get_label(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
        address = request.form.get("address", "")
        label = wallet.getlabel(address)
        return {
            "address": address,
            "label": label,
        }
    except Exception as e:
        handle_exception(e)
        return {
            "success": False,
            "error": f"Exception trying to get address label: Error: {e}",
        }


@wallets_endpoint.route("/wallet/<wallet_alias>/set_label", methods=["POST"])
@login_required
def set_label(wallet_alias):

    wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    address = request.form["address"]
    label = request.form["label"].rstrip()
    wallet.setlabel(address, label)
    return {"success": True}


@wallets_endpoint.route("/wallet/<wallet_alias>/txlist", methods=["POST"])
@login_required
@app.csrf.exempt
def txlist(wallet_alias):
    wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    idx = int(request.form.get("idx", 0))
    limit = int(request.form.get("limit", 100))
    search = request.form.get("search", None)
    sortby = request.form.get("sortby", None)
    sortdir = request.form.get("sortdir", "asc")
    fetch_transactions = request.form.get("fetch_transactions", False)
    txlist = wallet.txlist(
        fetch_transactions=fetch_transactions,
        validate_merkle_proofs=app.specter.config.get("validate_merkle_proofs", False),
        current_blockheight=app.specter.info["blocks"],
    )
    return process_txlist(
        txlist, idx=idx, limit=limit, search=search, sortby=sortby, sortdir=sortdir
    )


@wallets_endpoint.route("/wallet/<wallet_alias>/utxo_list", methods=["POST"])
@login_required
@app.csrf.exempt
def utxo_list(wallet_alias):
    wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    idx = int(request.form.get("idx", 0))
    limit = int(request.form.get("limit", 100))
    search = request.form.get("search", None)
    sortby = request.form.get("sortby", None)
    sortdir = request.form.get("sortdir", "asc")
    txlist = wallet.full_utxo
    for tx in txlist:
        if not tx.get("label", None):
            tx["label"] = wallet.getlabel(tx["address"])
    return process_txlist(
        txlist, idx=idx, limit=limit, search=search, sortby=sortby, sortdir=sortdir
    )


@wallets_endpoint.route("/wallets_overview/txlist", methods=["POST"])
@login_required
@app.csrf.exempt
def wallets_overview_txlist():
    idx = int(request.form.get("idx", 0))
    limit = int(request.form.get("limit", 100))
    search = request.form.get("search", None)
    sortby = request.form.get("sortby", None)
    sortdir = request.form.get("sortdir", "asc")
    fetch_transactions = request.form.get("fetch_transactions", False)
    txlist = app.specter.wallet_manager.full_txlist(
        fetch_transactions=fetch_transactions,
        validate_merkle_proofs=app.specter.config.get("validate_merkle_proofs", False),
        current_blockheight=app.specter.info["blocks"],
    )
    return process_txlist(
        txlist, idx=idx, limit=limit, search=search, sortby=sortby, sortdir=sortdir
    )


@wallets_endpoint.route("/wallets_overview/utxo_list", methods=["POST"])
@login_required
@app.csrf.exempt
def wallets_overview_utxo_list():
    idx = int(request.form.get("idx", 0))
    limit = int(request.form.get("limit", 100))
    search = request.form.get("search", None)
    sortby = request.form.get("sortby", None)
    sortdir = request.form.get("sortdir", "asc")
    fetch_transactions = request.form.get("fetch_transactions", False)
    txlist = app.specter.wallet_manager.full_utxo()
    return process_txlist(
        txlist, idx=idx, limit=limit, search=search, sortby=sortby, sortdir=sortdir
    )


@wallets_endpoint.route("/wallet/<wallet_alias>/addresses_list/", methods=["POST"])
@login_required
@app.csrf.exempt
def addresses_list(wallet_alias):
    """Return a JSON with keys:
        addressesList: list of addresses with the properties
                       (index, address, label, used, utxo, amount)
        pageCount: total number of pages
    POST parameters:
        idx: pagination index (current page)
        limit: maximum number of items on the page
        sortby: field by which the list will be ordered
                (index, address, label, used, utxo, amount)
        sortdir: 'asc' (ascending) or 'desc' (descending) order
        addressType: the current tab address type ('receive' or 'change')"""
    wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)

    idx = int(request.form.get("idx", 0))
    limit = int(request.form.get("limit", 100))
    sortby = request.form.get("sortby", None)
    sortdir = request.form.get("sortdir", "asc")
    address_type = request.form.get("addressType", "receive")

    addresses_list = wallet.addresses_info(address_type == "change")

    result = process_addresses_list(
        addresses_list, idx=idx, limit=limit, sortby=sortby, sortdir=sortdir
    )

    return {
        "addressesList": json.dumps(result["addressesList"]),
        "pageCount": result["pageCount"],
    }


@wallets_endpoint.route("/wallet/<wallet_alias>/addressinfo/", methods=["POST"])
@login_required
@app.csrf.exempt
def addressinfo(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
        address = request.form.get("address", "")
        if address:
            descriptor = wallet.get_descriptor(address=address)
            address_info = wallet.get_address_info(address=address)
            return {
                "success": True,
                "address": address,
                "descriptor": descriptor,
                "walletName": wallet.name,
                "isMine": not address_info.is_external,
                **address_info,
            }
    except Exception as e:

        app.logger.warning("Failed to fetch address data. Exception: {}".format(e))
    return {"success": False}


################## Wallet CSV export data endpoints #######################
# Export wallet addresses list
@wallets_endpoint.route("/wallet/<wallet_alias>/addresses_list.csv")
@login_required
def addresses_list_csv(wallet_alias):
    """Return a CSV with addresses of the <wallet_alias> containing the
    information: index, address, type, label, used, utxo and amount
    of each of them.
    GET parameters: sortby: field by which the CSV will be ordered
                            (index, address, label, used, utxo, amount)
                    sortdir: 'asc' (ascending) or 'desc' (descending) order
                    address_type: the current tab address type ('receive' or 'change')
                    onlyCurrentType: show all addresses (if false) or just the current
                                     type (address_type param)"""

    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)

        sortby = request.args.get("sortby", "index")
        sortdir = request.args.get("sortdir", "asc")
        address_type = request.args.get("addressType", "receive")
        only_current_type = request.args.get("onlyCurrentType", "false") == "true"

        if not only_current_type:
            receive_list = wallet.addresses_info(False)
            change_list = wallet.addresses_info(True)

            receive_result = process_addresses_list(
                receive_list, idx=0, limit=0, sortby=sortby, sortdir=sortdir
            )

            change_result = process_addresses_list(
                change_list, idx=0, limit=0, sortby=sortby, sortdir=sortdir
            )

            addressesList = (
                receive_result["addressesList"] + change_result["addressesList"]
            )
        else:
            addresses_list = wallet.addresses_info(address_type == "change")

            result = process_addresses_list(
                addresses_list, idx=0, limit=0, sortby=sortby, sortdir=sortdir
            )

            addressesList = result["addressesList"]

        # stream the response as the data is generated
        response = Response(
            wallet_addresses_list_to_csv(addressesList),
            mimetype="text/csv",
        )
        # add a filename
        response.headers.set(
            "Content-Disposition", "attachment", filename="addresses_list.csv"
        )
        return response
    except Exception as e:
        app.logger.error("Failed to export addresses list. Error: %s" % e)
        flash("Failed to export addresses list. Error: %s" % e, "error")
        return redirect(url_for("index"))


# Export wallet transaction history
@wallets_endpoint.route("/wallet/<wallet_alias>/transactions.csv")
@login_required
def tx_history_csv(wallet_alias):
    wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    validate_merkle_proofs = app.specter.config.get("validate_merkle_proofs", False)
    txlist = wallet.txlist(validate_merkle_proofs=validate_merkle_proofs)
    search = request.args.get("search", None)
    sortby = request.args.get("sortby", "time")
    sortdir = request.args.get("sortdir", "desc")
    txlist = json.loads(
        process_txlist(
            txlist, idx=0, limit=0, search=search, sortby=sortby, sortdir=sortdir
        )["txlist"]
    )
    includePricesHistory = request.args.get("exportPrices", "false") == "true"

    # stream the response as the data is generated
    response = Response(
        txlist_to_csv(wallet, txlist, app.specter, current_user, includePricesHistory),
        mimetype="text/csv",
    )
    # add a filename
    response.headers.set(
        "Content-Disposition", "attachment", filename="transactions.csv"
    )
    return response


# Export wallet UTXO list
@wallets_endpoint.route("/wallet/<wallet_alias>/utxo.csv")
@login_required
def utxo_csv(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
        includePricesHistory = request.args.get("exportPrices", "false") == "true"
        search = request.args.get("search", None)
        sortby = request.args.get("sortby", "time")
        sortdir = request.args.get("sortdir", "desc")
        txlist = json.loads(
            process_txlist(
                wallet.full_utxo,
                idx=0,
                limit=0,
                search=search,
                sortby=sortby,
                sortdir=sortdir,
            )["txlist"]
        )
        # stream the response as the data is generated
        response = Response(
            txlist_to_csv(
                wallet,
                txlist,
                app.specter,
                current_user,
                includePricesHistory,
            ),
            mimetype="text/csv",
        )
        # add a filename
        response.headers.set("Content-Disposition", "attachment", filename="utxo.csv")
        return response
    except Exception as e:
        logging.exception(e)
        return "Failed to export wallet utxo. Error: %s" % e, 500


# Export all wallets transaction history combined
@wallets_endpoint.route("/wallets_overview/full_transactions.csv")
@login_required
def wallet_overview_txs_csv():
    try:
        validate_merkle_proofs = app.specter.config.get("validate_merkle_proofs", False)
        txlist = app.specter.wallet_manager.full_txlist(
            validate_merkle_proofs=validate_merkle_proofs,
        )
        search = request.args.get("search", None)
        sortby = request.args.get("sortby", "time")
        sortdir = request.args.get("sortdir", "desc")
        txlist = json.loads(
            process_txlist(
                txlist, idx=0, limit=0, search=search, sortby=sortby, sortdir=sortdir
            )["txlist"]
        )
        includePricesHistory = request.args.get("exportPrices", "false") == "true"
        # stream the response as the data is generated
        response = Response(
            txlist_to_csv(
                None, txlist, app.specter, current_user, includePricesHistory
            ),
            mimetype="text/csv",
        )
        # add a filename
        response.headers.set(
            "Content-Disposition", "attachment", filename="full_transactions.csv"
        )
        return response
    except Exception as e:
        logging.exception(e)
        return "Failed to export wallets overview history. Error: %s" % e, 500


# Export all wallets transaction history combined
@wallets_endpoint.route("/wallets_overview/full_utxo.csv")
@login_required
def wallet_overview_utxo_csv():
    try:
        txlist = app.specter.wallet_manager.full_utxo()
        search = request.args.get("search", None)
        sortby = request.args.get("sortby", "time")
        sortdir = request.args.get("sortdir", "desc")
        txlist = json.loads(
            process_txlist(
                txlist, idx=0, limit=0, search=search, sortby=sortby, sortdir=sortdir
            )["txlist"]
        )
        includePricesHistory = request.args.get("exportPrices", "false") == "true"
        # stream the response as the data is generated
        response = Response(
            txlist_to_csv(
                None, txlist, app.specter, current_user, includePricesHistory
            ),
            mimetype="text/csv",
        )
        # add a filename
        response.headers.set(
            "Content-Disposition", "attachment", filename="full_utxo.csv"
        )
        return response
    except Exception as e:
        logging.exception(e)
        return "Failed to export wallets overview utxo. Error: %s" % e, 500


################## Helpers #######################

# Transactions list to user-friendly CSV format
def txlist_to_csv(wallet, _txlist, specter, current_user, includePricesHistory=False):
    txlist = []
    for tx in _txlist:
        if isinstance(tx["address"], list):
            _tx = tx.copy()
            for i in range(0, len(tx["address"])):
                _tx["address"] = tx["address"][i]
                _tx["amount"] = tx["amount"][i]
                txlist.append(_tx.copy())
        else:
            txlist.append(tx.copy())
    data = StringIO()
    w = csv.writer(data)
    # write header
    symbol = "USD"
    if specter.price_provider.endswith("_eur"):
        symbol = "EUR"
    elif specter.price_provider.endswith("_gbp"):
        symbol = "GBP"
    row = (
        "Date",
        "Label",
        "Category",
        "Amount ({})".format(specter.unit.upper()),
        "Value ({})".format(symbol),
        "Rate (BTC/{})".format(symbol)
        if specter.unit != "sat"
        else "Rate ({}/SAT)".format(symbol),
        "TxID",
        "Address",
        "Block Height",
        "Timestamp",
        "Raw Transaction",
    )
    if not wallet:
        row = ("Wallet",) + row
    w.writerow(row)
    yield data.getvalue()
    data.seek(0)
    data.truncate(0)

    # write each log item
    _wallet = wallet
    for tx in txlist:
        if not wallet:
            wallet_alias = tx.get("wallet_alias", None)
            try:
                _wallet = specter.wallet_manager.get_by_alias(wallet_alias)
            except Exception as e:
                continue
        label = _wallet.getlabel(tx["address"])
        if label == tx["address"]:
            label = ""
        tx_raw = _wallet.gettransaction(tx["txid"])
        if tx_raw:
            tx_hex = tx_raw["hex"]
        else:
            tx_hex = ""
        if not tx.get("blockheight", None):
            if tx_raw.get("blockheight", None):
                tx["blockheight"] = tx_raw["blockheight"]
            else:
                tx["blockheight"] = "Unconfirmed"
        if specter.unit == "sat":
            value = float(tx["amount"])
            tx["amount"] = round(value * 1e8)
        if includePricesHistory:
            success, rate, symbol = get_price_at(
                specter, current_user, timestamp=tx["time"]
            )
        else:
            success = False
        if success:
            rate = float(rate)
            if specter.unit == "sat":
                rate = rate / 1e8
            amount_price = float(tx["amount"]) * rate
            if specter.unit == "sat":
                rate = round(1 / rate)
        else:
            amount_price = None
            rate = "-"

        row = (
            time.strftime("%Y-%m-%d", time.localtime(tx["time"])),
            label,
            tx["category"],
            round(tx["amount"], (0 if specter.unit == "sat" else 8)),
            round(amount_price * 100) / 100 if amount_price is not None else "-",
            rate,
            tx["txid"],
            tx["address"],
            tx["blockheight"],
            tx["time"],
            tx_hex,
        )
        if not wallet:
            row = (tx.get("wallet_alias", ""),) + row
        w.writerow(row)
        yield data.getvalue()
        data.seek(0)
        data.truncate(0)


# Addresses list to user-friendly CSV format
def addresses_list_to_csv(wallet):
    data = StringIO()
    w = csv.writer(data)
    # write header
    row = (
        "Address",
        "Label",
        "Index",
        "Used",
        "Current balance",
    )
    w.writerow(row)
    yield data.getvalue()
    data.seek(0)
    data.truncate(0)

    # write each log item
    for address in wallet._addresses:
        address_info = wallet.get_address_info(address)
        if not address_info.is_labeled and not address_info.used:
            continue
        row = (
            address,
            address_info.label,
            "(external)"
            if address_info.is_external
            else (
                str(address_info.index) + (" (change)" if address_info.change else "")
            ),
            address_info.used,
        )
        if address_info.is_external:
            balance_on_address = "unknown (external address)"
        else:
            balance_on_address = 0
            if address_info.used:
                for tx in wallet.full_utxo:
                    if tx.get("address", "") == address:
                        balance_on_address += tx.get("amount", 0)
        row += (balance_on_address,)

        w.writerow(row)
        yield data.getvalue()
        data.seek(0)
        data.truncate(0)


def wallet_addresses_list_to_csv(addresses_list):
    """Convert a list of the wallet addresses to user-friendly CSV format
    Parameters: addresses_list: a dict of addresses informations
                (index, address, type, label, used, utxo and amount)"""
    data = StringIO()
    w = csv.writer(data)
    # write header
    row = (
        "Index",
        "Address",
        "Type",
        "Label",
        "Used",
        "UTXO",
        "Amount (BTC)",
    )
    w.writerow(row)
    yield data.getvalue()
    data.seek(0)
    data.truncate(0)

    # write each log item
    for address_item in addresses_list:

        used = "Yes" if address_item["used"] else "No"

        row = (
            address_item["index"],
            address_item["address"],
            address_item["type"],
            address_item["label"],
            used,
            address_item["utxo"],
            address_item["amount"],
        )

        w.writerow(row)
        yield data.getvalue()
        data.seek(0)
        data.truncate(0)


def process_txlist(txlist, idx=0, limit=100, search=None, sortby=None, sortdir="asc"):
    if search:
        txlist = [
            tx
            for tx in txlist
            if search in tx["txid"]
            or (
                any(search in address for address in tx["address"])
                if isinstance(tx["address"], list)
                else search in tx["address"]
            )
            or (
                any(search in label for label in tx["label"])
                if isinstance(tx["label"], list)
                else search in tx["label"]
            )
            or (
                any(search in str(amount) for amount in tx["amount"])
                if isinstance(tx["amount"], list)
                else search in str(tx["amount"])
            )
            or search in str(tx["confirmations"])
            or search in str(tx["time"])
            or search
            in str(format(datetime.fromtimestamp(tx["time"]), "%d.%m.%Y %H:%M"))
        ]
    if sortby:

        def sort(tx):
            val = tx.get(sortby, None)
            final = val
            if val:
                if isinstance(val, list):
                    if isinstance(val[0], Number):
                        final = sum(val)
                    elif isinstance(val[0], str):
                        final = sorted(
                            val, key=lambda s: s.lower(), reverse=sortdir != "asc"
                        )[0].lower()
                elif isinstance(val, str):
                    final = val.lower()
            return final

        txlist = sorted(txlist, key=sort, reverse=sortdir != "asc")
    if limit:
        page_count = (len(txlist) // limit) + (0 if len(txlist) % limit == 0 else 1)
        txlist = txlist[limit * idx : limit * (idx + 1)]
    else:
        page_count = 1
    return {"txlist": json.dumps(txlist), "pageCount": page_count}


def process_addresses_list(
    addresses_list, idx=0, limit=100, sortby=None, sortdir="asc"
):
    """Receive an address list as parameter and sort it or slice it for pagination.
    Parameters: addresses_list: list of dict with the keys
                                (index, address, label, used, utxo, amount)
                idx: pagination index (current page)
                limit: maximum number of items on the page
                sortby: field by which the list will be ordered
                        (index, address, label, used, utxo, amount)
                sortdir: 'asc' (ascending) or 'desc' (descending) order"""
    if sortby:

        def sort(addr):
            val = addr.get(sortby, None)
            final = val
            if val:
                if isinstance(val, str):
                    final = val.lower()
            return final

        addresses_list = sorted(addresses_list, key=sort, reverse=sortdir != "asc")

    if limit:
        page_count = (len(addresses_list) // limit) + (
            0 if len(addresses_list) % limit == 0 else 1
        )
        addresses_list = addresses_list[limit * idx : limit * (idx + 1)]
    else:
        page_count = 1

    return {"addressesList": addresses_list, "pageCount": page_count}

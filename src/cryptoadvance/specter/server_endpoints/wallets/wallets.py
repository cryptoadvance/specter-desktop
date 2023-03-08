import json
import logging
import random
from functools import wraps

import requests
from flask import Blueprint
from flask import current_app as app
from flask import jsonify, redirect, render_template, request, url_for
from flask_babel import lazy_gettext as _
from flask_login import login_required

from ...commands.psbt_creator import PsbtCreator
from ...helpers import bcur2base64, get_devices_with_keys_by_type, get_txid, alias
from ...key import Key
from ...managers.wallet_manager import purposes
from ...persistence import delete_file
from ...server_endpoints import flash
from ...services import callbacks
from ...services.callbacks import adjust_view_model
from ...specter_error import SpecterError, handle_exception
from ...util.tx import convert_rawtransaction_to_psbt, is_hex
from ...util.wallet_importer import WalletImporter
from ...wallet import Wallet
from .wallets_vm import WalletsOverviewVm

logger = logging.getLogger(__name__)

rand = random.randint(0, 1e32)  # to force style refresh

# Setup endpoint blueprint
wallets_endpoint = Blueprint("wallets_endpoint", __name__)


def handle_wallet_error(func_name, error):
    flash(_("SpecterError while {}: {}").format(func_name, error), "error")
    app.logger.error(f"SpecterError while {func_name}: {error}")
    app.specter.wallet_manager.update(comment="via handle_wallet_error")
    return redirect(url_for("welcome_endpoint.about"))


def check_wallet(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        """checks the wallet for healthiness A wrapper function"""
        if kwargs["wallet_alias"]:
            wallet_alias = kwargs["wallet_alias"]
            wallet: Wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
            wallet.get_info()
        return func(*args, **kwargs)

    return wrapper


@wallets_endpoint.context_processor
def inject_common_stuff():
    """Can be used in all jinja2 templates of this Blueprint
    Injects the additional wallet_tabs via extentions
    """
    ext_wallettabs = app.specter.service_manager.execute_ext_callbacks(
        callbacks.add_wallettabs
    )
    return dict(ext_wallettabs=ext_wallettabs)


################## Wallet overview #######################


@wallets_endpoint.route("/wallets_overview/")
@login_required
def wallets_overview():
    app.specter.check_blockheight()
    # The execute_ext_callbacks method is not really prepared for the things we're doing here.
    # that's why we need so many lines for just expressing:
    # "Here is a ViewModel, adjust it if you want"
    # We need to change that method to enable "middleware"
    wallets_overview_vm = app.specter.service_manager.execute_ext_callbacks(
        adjust_view_model, WalletsOverviewVm()
    )
    if wallets_overview_vm.wallets_overview_redirect != None:
        logger.info(f"redirecting to {wallets_overview_vm.wallets_overview_redirect}")
        return redirect(wallets_overview_vm.wallets_overview_redirect)

    wallet: Wallet
    for wallet in list(app.specter.wallet_manager.wallets.values()):
        wallet.update_balance()
        wallet.check_utxo()

    return render_template(
        "wallet/overview/wallets_overview.jinja",
        specter=app.specter,
        rand=rand,
        services=app.specter.service_manager.services,
        wallets_overview_vm=wallets_overview_vm,
    )


################## Failed wallets fix #######################


@wallets_endpoint.route("/failed_wallets/", methods=["POST"])
@login_required
def failed_wallets():
    if request.method == "POST":
        action = request.form["action"]
        if action == "retry_loading_wallets":
            app.specter.wallet_manager.update(
                comment="via failed_wallets_retry_loading_wallets"
            )
        elif action == "delete_failed_wallet":
            try:
                wallet = json.loads(request.form["wallet_data"])
                fullpath = wallet["fullpath"]
                delete_file(fullpath)
                delete_file(fullpath + ".bkp")
                delete_file(fullpath.replace(".json", "_addr.csv"))
                delete_file(fullpath.replace(".json", "_txs.csv"))
                app.specter.wallet_manager.update(
                    comment="via failed_wallets_delete_failed_wallet"
                )
            except Exception as e:
                handle_exception(e)
                flash(_("Failed to delete wallet: {}").format(str(e)), "error")
    return redirect("/")


################## New wallet #######################


@wallets_endpoint.route("/new_wallet/")
@login_required
def new_wallet_type():
    err = None
    if not app.specter.node.is_running:
        flash(_("You need a node connection to create wallets."), "error")
        return redirect(url_for("nodes_endpoint.node_settings_new_node_get"))
    try:
        # Make sure wallet is enabled on Bitcoin Core
        app.specter.rpc.listwallets()
    except RpcError as e:
        handle_exception(e)
        # Hmm, would be better to be more precise with this exception. Best assumption:
        err = _(
            '<p><br>Bitcoin Core is running with wallets disabled.<br><br>Please make sure disablewallet is off (set disablewallet=0 in your bitcoin.conf), then restart Bitcoin Core and try again.<br>See <a href="https://github.com/cryptoadvance/specter-desktop/blob/34ca139694ecafb2e7c2bd5ad5c4ac74c6d11501/docs/faq.md#im-not-sure-i-want-the-bitcoin-core-wallet-functionality-to-be-used-is-that-mandatory-if-so-is-it-considered-secure" target="_blank" style="color: white;">here</a> for more information.</p>'
        )
        return render_template("base.jinja", error=err, specter=app.specter, rand=rand)
    return render_template(
        "wallet/new_wallet/new_wallet_type.jinja", specter=app.specter, rand=rand
    )


@wallets_endpoint.route("/new_wallet/<wallet_type>/", methods=["GET", "POST"])
@login_required
def new_wallet(wallet_type):
    wallet_types = ["simple", "multisig", "import_wallet"]
    if wallet_type not in wallet_types:
        flash(_("Unknown wallet type requested"), "error")
        return redirect(url_for("wallets_endpoint.new_wallet_type"))

    err = None
    if request.method == "POST":
        action = request.form["action"]
        if action == "importwallet":
            try:
                wallet_importer: WalletImporter = WalletImporter(
                    request.form["wallet_data"],
                    app.specter,
                )
            except SpecterError as se:
                flash(str(se), "error")
                return redirect(url_for("wallets_endpoint.new_wallet_type"))
            createwallet = "createwallet" in request.form
            if createwallet:
                # User might have renamed it
                wallet_importer.wallet_name = request.form["wallet_name"]
                wallet_importer.create_nonexisting_signers(
                    app.specter.device_manager, request.form
                )
                try:
                    wallet_importer.create_wallet(app.specter.wallet_manager)
                except SpecterError as se:
                    flash(str(se), "error")
                    return redirect(url_for("wallets_endpoint.new_wallet_type"))
                flash(_("Wallet imported successfully"), "info")
                try:
                    wallet_importer.rescan_as_needed(app.specter)
                except SpecterError as se:
                    flash(str(se), "error")
                return redirect(
                    url_for(
                        "wallets_endpoint.receive",
                        wallet_alias=wallet_importer.wallet.alias,
                    )
                    + "?newwallet=true"
                )
            else:
                return render_template(
                    "wallet/new_wallet/import_wallet.jinja",
                    wallet_data=wallet_importer.wallet_json,
                    wallet_type=wallet_importer.wallet_type,
                    wallet_name=wallet_importer.wallet_name,
                    cosigners=wallet_importer.cosigners,
                    unknown_cosigners=wallet_importer.unknown_cosigners,
                    unknown_cosigners_types=wallet_importer.unknown_cosigners_types,
                    sigs_required=wallet_importer.sigs_required,
                    sigs_total=wallet_importer.sigs_total,
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
                    error=_(
                        "No device was selected. Please select a device to create the wallet for."
                    ),
                    specter=app.specter,
                    rand=rand,
                )
            devices = get_devices_with_keys_by_type(app, cosigners, wallet_type)
            for device in devices:
                if len(device.keys) == 0:
                    err = _(
                        "Device {} doesn't have keys matching this wallet type"
                    ).format(device.name)
                    break

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
            if alias(wallet_name) in app.specter.wallet_manager.wallets_aliases:
                err = _("Wallet name already exists. Choose a different name!")
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
                err = _(
                    "No keys were selected for device, please try adding keys first"
                )
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
                wallet: Wallet = app.specter.wallet_manager.create_wallet(
                    wallet_name, sigs_required, address_type, keys, cosigners
                )
            except Exception as e:
                handle_exception(e)
                err = _("Failed to create wallet. Error: {}").format(e)
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
                        app.specter.requests_session(
                            explorer and explorer.endswith(".onion")
                        ),
                        app.specter.only_tor,
                    )
                    app.specter.info["utxorescan"] = 1
                    app.specter.utxorescanwallet = wallet.alias
                else:
                    app.logger.info("Rescanning Blockchain ...")
                    startblock = int(request.form["startblock"])
                    try:
                        wallet.rpc.rescanblockchain(startblock, no_wait=True)
                    except Exception as e:
                        handle_exception(e)
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
    wallet: Wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    if wallet.amount_total > 0:
        return redirect(url_for("wallets_endpoint.history", wallet_alias=wallet_alias))
    else:
        return redirect(url_for("wallets_endpoint.receive", wallet_alias=wallet_alias))


###### Wallet transaction history ######
@wallets_endpoint.route("/wallet/<wallet_alias>/history/", methods=["GET", "POST"])
@login_required
def history(wallet_alias):
    wallet: Wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
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
    wallet.update_balance()
    wallet.check_utxo()

    return render_template(
        "wallet/history/wallet_history.jinja",
        wallet_alias=wallet_alias,
        wallet=wallet,
        tx_list_type=tx_list_type,
        specter=app.specter,
        rand=rand,
        services=app.specter.service_manager.services,
    )


###### Wallet receive ######


@wallets_endpoint.route("/wallet/<wallet_alias>/receive/", methods=["GET", "POST"])
@login_required
@check_wallet
def receive(wallet_alias):
    wallet: Wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
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
    wallet: Wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    if len(wallet.pending_psbts) > 0:
        return redirect(
            url_for("wallets_endpoint.send_pending", wallet_alias=wallet_alias)
        )
    else:
        return redirect(url_for("wallets_endpoint.send_new", wallet_alias=wallet_alias))


@wallets_endpoint.route("/wallet/<wallet_alias>/send/new", methods=["GET", "POST"])
@login_required
def send_new(wallet_alias):
    wallet: Wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    # update balances in the wallet
    wallet.update_balance()
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
    fillform = False
    subtract = False
    subtract_from = 0
    fee_options = "dynamic"
    rbf = not app.specter.is_liquid
    rbf_utxo = []
    rbf_tx_id = ""
    selected_coins = request.form.getlist("coinselect")
    # Additional server side check not to use frozen UTXO as a precaution
    frozen_utxo = wallet.frozen_utxo
    for utxo in selected_coins:
        if utxo in frozen_utxo:
            selected_coins.remove(utxo)
            flash(f"You've selected a frozen UTXO for a transaction.", "error")
            return redirect(
                url_for("wallets_endpoint.history", wallet_alias=wallet_alias)
            )

    if request.method == "POST":
        action = request.form.get("action")
        rbf_tx_id = request.form.get("rbf_tx_id", "")
        if action == "createpsbt":
            psbt_creator = PsbtCreator(
                app.specter,
                wallet,
                request.form.get("ui_option", "ui"),
                request_form=request.form,
                recipients_txt=request.form["recipients"],
                recipients_amount_unit=request.form.get("amount_unit_text"),
            )
            psbt = psbt_creator.create_psbt(wallet)
            return render_template(
                "wallet/send/sign/wallet_send_sign_psbt.jinja",
                psbt=psbt,
                labels=labels,
                wallet_alias=wallet_alias,
                wallet=wallet,
                specter=app.specter,
                rand=rand,
            )

        elif action in ["rbf", "rbf_cancel"]:
            try:
                rbf_tx_id = request.form["rbf_tx_id"]
                rbf_fee_rate = float(request.form["rbf_fee_rate"])

                if action == "rbf":
                    psbt = wallet.bumpfee(rbf_tx_id, rbf_fee_rate)
                elif action == "rbf_cancel":
                    psbt = wallet.canceltx(rbf_tx_id, rbf_fee_rate)
                else:
                    raise SpecterError("Invalid action")

                if psbt["fee_rate"] - rbf_fee_rate > wallet.MIN_FEE_RATE / 10:
                    flash(
                        _(
                            "We had to increase the fee rate from {} to {} sat/vbyte"
                        ).format(rbf_fee_rate, psbt["fee_rate"])
                    )
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
                handle_exception(e)
                flash(_("Failed to perform RBF. Error: {}").format(e), "error")
                return redirect(
                    url_for("wallets_endpoint.history", wallet_alias=wallet_alias)
                )
        elif action == "rbf_edit":
            try:
                decoded_tx = wallet.decode_tx(rbf_tx_id)
                addresses = decoded_tx["addresses"]
                amounts = decoded_tx["amounts"]
                amount_units = decoded_tx.get("assets", ["btc"] * len(addresses))
                # get_label returns a label or address if no label is set
                labels = [wallet.getlabel(addr) for addr in addresses]
                # set empty label to addresses that don't have labels
                labels = [
                    label if label != addr else ""
                    for addr, label in zip(addresses, labels)
                ]

                selected_coins = [
                    f"{utxo['txid']}, {utxo['vout']}"
                    for utxo in decoded_tx["used_utxo"]
                ]
                fee_rate = float(request.form["rbf_fee_rate"])
                fee_options = "manual"
                rbf = True
                fillform = True
            except Exception as e:
                handle_exception(e)
                flash(_("Failed to perform RBF. Error: {}").format(e), "error")
        elif action == "signhotwallet":
            passphrase = request.form["passphrase"]
            psbt = json.loads(request.form["psbt"])
            current_psbt = wallet.pending_psbts[psbt["tx"]["txid"]]
            b64psbt = str(current_psbt)
            device = request.form["device"]
            if "devices_signed" not in psbt or device not in psbt["devices_signed"]:
                try:
                    # get device and sign with it
                    signed_psbt = app.specter.device_manager.get_by_alias(
                        device
                    ).sign_psbt(b64psbt, wallet, passphrase)
                    raw = None
                    if signed_psbt["complete"]:
                        raw = wallet.rpc.finalizepsbt(b64psbt)
                    current_psbt.update(signed_psbt["psbt"], raw)
                    signed_psbt = signed_psbt["psbt"]
                    psbt = current_psbt.to_dict()
                except Exception as e:
                    handle_exception(e)
                    signed_psbt = None
                    flash(_("Failed to sign PSBT: {}").format(e), "error")
            else:
                signed_psbt = None
                flash(_("Device already signed the PSBT"), "error")
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
        elif action == "fillform":
            # TODO: Not yet used. Remove if the use case doesn't happen.
            # can be used to recommend a transaction from a service (goind to an exchange or so)
            addresses = request.form.getlist("addresses[]")
            labels = request.form.getlist("labels[]")
            amounts = request.form.getlist("amounts[]")
            fillform = True

    if rbf_tx_id:
        try:
            rbf_utxo = wallet.get_rbf_utxo(rbf_tx_id)
        except Exception as e:
            handle_exception(e)
            flash(_("Failed to get RBF coins. Error: {}").format(e), "error")

    show_advanced_settings = (
        ui_option != "ui" or subtract or fee_options != "dynamic" or not rbf
    )
    wallet_utxo = wallet.utxo
    if app.specter.is_liquid:
        for tx in wallet_utxo + rbf_utxo:
            if "asset" in tx:
                tx["assetlabel"] = app.specter.asset_label(tx.get("asset"))
    return render_template(
        "wallet/send/new/wallet_send.jinja",
        psbt=psbt,
        ui_option=ui_option,
        recipients_txt=recipients_txt,
        addresses=addresses,
        labels=labels,
        amounts=amounts,
        fillform=fillform,
        recipients=list(zip(addresses, amounts, amount_units, labels)),
        subtract=subtract,
        subtract_from=subtract_from,
        fee_options=fee_options,
        rbf=rbf,
        selected_coins=selected_coins,
        show_advanced_settings=show_advanced_settings,
        rbf_utxo=rbf_utxo,
        rbf_tx_id=rbf_tx_id,
        wallet_utxo=wallet_utxo,
        wallet_alias=wallet_alias,
        wallet=wallet,
        specter=app.specter,
        rand=rand,
        error=err,
    )


@wallets_endpoint.route("/wallet/<wallet_alias>/send/pending/", methods=["GET", "POST"])
@login_required
def send_pending(wallet_alias):
    wallet: Wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    if request.method == "POST":
        action = request.form["action"]
        if action == "deletepsbt":
            try:
                wallet.delete_pending_psbt(
                    json.loads(request.form["pending_psbt"])["tx"]["txid"]
                )
            except Exception as e:
                handle_exception(e)
                flash(_("Could not delete Pending PSBT!"), "error")
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
    pending_psbts = wallet.pending_psbts_dict()
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
    wallet: Wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    if request.method == "POST":
        action = request.form["action"]
        if action == "importpsbt":
            try:
                b64psbt = "".join(request.form["rawpsbt"].split())
                psbt = wallet.importpsbt(
                    convert_rawtransaction_to_psbt(wallet.rpc, b64psbt)
                    if is_hex(b64psbt)
                    else b64psbt
                )
            except Exception as e:
                handle_exception(e)
                flash(_("Could not import PSBT: {}").format(e), "error")
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
    wallet: Wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)

    # update balances in the wallet
    app.specter.check_blockheight()
    wallet.update_balance()
    wallet.check_utxo()

    return render_template(
        "wallet/addresses/wallet_addresses.jinja",
        wallet_alias=wallet_alias,
        wallet=wallet,
        specter=app.specter,
        rand=rand,
        services=app.specter.service_manager.services,
    )


###### Wallet settings ######


@wallets_endpoint.route("/wallet/<wallet_alias>/settings/", methods=["GET", "POST"])
# In case of exceptions in the "subactions" POST method handlers, the error-handler
# will redirect to the same endpoint but GET-method. Specifying them here:
@wallets_endpoint.route(
    "/wallet/<wallet_alias>/settings/importaddresslabels", methods=["GET"]
)
@wallets_endpoint.route(
    "/wallet/<wallet_alias>/settings/keypoolrefill", methods=["GET"]
)
@wallets_endpoint.route("/wallet/<wallet_alias>/settings/rescan", methods=["GET"])
@wallets_endpoint.route("/wallet/<wallet_alias>/settings/deletewallet", methods=["GET"])
@wallets_endpoint.route("/wallet/<wallet_alias>/settings/clearcache", methods=["GET"])
@login_required
def settings(wallet_alias):
    wallet: Wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    if request.method == "POST":
        action = request.form["action"]
        # Would like to refactor this to another endpoint as well
        # but that's not so easy as the ui part is also used elsewhere
        if action == "rename":
            wallet_name = request.form["newtitle"]
            if not wallet_name:
                flash(_("Wallet name cannot be empty"), "error")
            elif wallet_name == wallet.name:
                pass
            elif alias(wallet_name) in app.specter.wallet_manager.wallets_aliases:
                flash(
                    _("Wallet name already exists. Choose a different name!"), "error"
                )
            else:
                app.specter.wallet_manager.rename_wallet(wallet, wallet_name)
                flash("Wallet successfully renamed!")
        else:
            flash(f"Unknown action: {action}")
    return render_template(
        "wallet/settings/wallet_settings.jinja",
        purposes=purposes,
        wallet_alias=wallet_alias,
        wallet=wallet,
        specter=app.specter,
        rand=rand,
        scroll_to_rescan_blockchain=request.args.get("rescan_blockchain"),
    )


@wallets_endpoint.route(
    "/wallet/<wallet_alias>/settings/importaddresslabels", methods=["POST"]
)
@login_required
def settings_importaddresslabels(wallet_alias):
    wallet: Wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    action = request.form["action"]
    address_labels = request.form["address_labels_data"]
    imported_addresses_len = wallet.import_address_labels(address_labels)
    if imported_addresses_len > 1:
        flash(f"Successfully imported {imported_addresses_len} address labels.")
    elif imported_addresses_len == 1:
        flash(f"Successfully imported {imported_addresses_len} address label.")
    else:
        flash("No address labels were imported.")
    return redirect(url_for("wallets_endpoint.settings"))


@wallets_endpoint.route(
    "/wallet/<wallet_alias>/settings/keypoolrefill", methods=["POST"]
)
@login_required
def settings_keypoolrefill(wallet_alias):
    wallet: Wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    delta = int(request.form["keypooladd"])
    wallet.keypoolrefill(wallet.keypool, wallet.keypool + delta)
    wallet.keypoolrefill(
        wallet.change_keypool, wallet.change_keypool + delta, change=True
    )
    wallet.getdata()
    return render_template(
        "wallet/settings/wallet_settings.jinja",
        purposes=purposes,
        wallet_alias=wallet_alias,
        wallet=wallet,
        specter=app.specter,
        rand=rand,
        scroll_to_rescan_blockchain=request.args.get("rescan_blockchain"),
    )


@wallets_endpoint.route("/wallet/<wallet_alias>/settings/rescan", methods=["POST"])
@login_required
def settings_rescan(wallet_alias):
    wallet: Wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    error = None
    action = request.form["action"]
    if action == "rescanblockchain":
        startblock = int(request.form["startblock"])
        try:
            delete_file(wallet._transactions.path)
            wallet.fetch_transactions()

            # This rpc call does not seem to return a result; use no_wait to ignore timeout errors
            wallet.rpc.rescanblockchain(startblock, no_wait=True)
        except Exception as e:
            handle_exception(e)
            error = "%r" % e
        wallet.getdata()
    elif action == "abortrescan":
        res = wallet.rpc.abortrescan()
        if not res:
            error = _("Failed to abort rescan. Maybe already complete?")
        wallet.getdata()
    elif action == "rescanutxo":
        explorer = None
        if "use_explorer" in request.form:
            if request.form["explorer"] == "CUSTOM":
                explorer = request.form["custom_explorer"]
            else:
                explorer = app.config["EXPLORERS_LIST"][request.form["explorer"]]["url"]
        wallet.rescanutxo(
            explorer,
            app.specter.requests_session(explorer and explorer.endswith(".onion")),
            app.specter.only_tor,
        )
        app.specter.info["utxorescan"] = 1
        app.specter.utxorescanwallet = wallet.alias
        flash(
            "Rescan started. Check the status bar on the left for progress and/or the logs for potential issues."
        )
    elif action == "abortrescanutxo":
        app.specter.node.abortrescanutxo()
        app.specter.info["utxorescan"] = None
        app.specter.utxorescanwallet = None
        flash(_("Successfully aborted the UTXO rescan"))
    scroll_to_rescan_blockchain = request.args.get("rescan_blockchain")
    return render_template(
        "wallet/settings/wallet_settings.jinja",
        purposes=purposes,
        wallet_alias=wallet_alias,
        wallet=wallet,
        specter=app.specter,
        rand=rand,
        error=error,
        scroll_to_rescan_blockchain=scroll_to_rescan_blockchain,
    )


@wallets_endpoint.route(
    "/wallet/<wallet_alias>/settings/deletewallet", methods=["POST"]
)
@login_required
def settings_deletewallet(wallet_alias):
    wallet: Wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    error = None
    deleted = app.specter.wallet_manager.delete_wallet(wallet, app.specter.node)
    # deleted is a tuple: (specter_wallet_deleted, core_wallet_file_deleted)
    if deleted == (True, True):
        flash(_("Wallet in Specter and wallet file on node deleted successfully."))
        return redirect(url_for("index"))
    elif deleted == (True, False):
        flash(
            _(
                "Wallet in Specter deleted successfully but wallet file on node could not be removed automatically."
            )
        )
        return redirect(url_for("index"))
    elif deleted == (False, True):
        flash(
            _("Deletion of wallet in Specter failed, but wallet on node was removed."),
            "error",
        )
        return redirect(url_for("index"))
    else:
        flash(_("Deletion of wallet failed."), "error")
        return redirect(request.referrer or "/")


@wallets_endpoint.route("/wallet/<wallet_alias>/settings/clearcache", methods=["POST"])
@login_required
def settings_clearcache(wallet_alias):
    wallet: Wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    error = None
    wallet.clear_cache()
    flash("Cache with transactions cleared successfully!")
    scroll_to_rescan_blockchain = request.args.get("rescan_blockchain")
    return render_template(
        "wallet/settings/wallet_settings.jinja",
        purposes=purposes,
        wallet_alias=wallet_alias,
        wallet=wallet,
        specter=app.specter,
        rand=rand,
        error=error,
        scroll_to_rescan_blockchain=scroll_to_rescan_blockchain,
    )

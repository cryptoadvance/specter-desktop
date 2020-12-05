import ast, json, os, time, base64, random, requests
from ..util.tx import decoderawtransaction

from flask import (
    Flask,
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    flash,
)
from flask_login import login_required
from ..util.descriptor import AddChecksum, Descriptor
from ..helpers import (
    bcur2base64,
    get_devices_with_keys_by_type,
    get_txid,
    is_testnet,
    parse_wallet_data_import,
)
from ..key import Key
from ..specter import Specter
from ..specter_error import SpecterError
from ..wallet_manager import purposes
from ..rpc import RpcError
from binascii import b2a_base64
from ..util.base43 import b43_decode

from flask import current_app as app

rand = random.randint(0, 1e32)  # to force style refresh

# Setup endpoint blueprint
wallets_endpoint = Blueprint("wallets_endpoint", __name__)


################## Wallet overview #######################


@wallets_endpoint.route("/wallets_overview/")
@login_required
def wallets_overview():
    idx = int(request.args.get("idx", default=0))
    return render_template(
        "wallet/wallets_overview.jinja",
        idx=idx,
        history=True,
        specter=app.specter,
        rand=rand,
    )


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
        return redirect(url_for("new_wallet_type"))

    err = None
    if request.method == "POST":
        action = request.form["action"]
        if action == "importwallet":
            wallet_data = json.loads(request.form["wallet_data"].replace("'", "h"))
            try:
                (
                    wallet_name,
                    recv_descriptor,
                    cosigners_types,
                ) = parse_wallet_data_import(wallet_data)
            except Exception:
                flash("Unsupported wallet import format", "error")
                return redirect(url_for("new_wallet_type"))
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
                    return redirect(url_for("new_wallet_type"))
            except:
                flash("Invalid wallet descriptor.", "error")
                return redirect(url_for("new_wallet_type"))
            if wallet_name in app.specter.wallet_manager.wallets_names:
                flash("Wallet with the same name already exists", "error")
                return redirect(url_for("new_wallet_type"))

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
                wallet = app.specter.wallet_manager.create_wallet(
                    wallet_name, sigs_required, address_type, keys, cosigners
                )
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
                purposes=purposes,
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
                    purposes=purposes,
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
                    purposes=purposes,
                    cosigners=devices,
                    wallet_type=wallet_type,
                    sigs_total=len(devices),
                    sigs_required=max(len(devices) * 2 // 3, 1),
                    error=err,
                    specter=app.specter,
                    rand=rand,
                )

            # create a wallet here
            wallet = app.specter.wallet_manager.create_wallet(
                wallet_name, sigs_required, address_type, keys, cosigners
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
                        explorer = app.specter.get_default_explorer()
                    wallet.rescanutxo(explorer)
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
                purposes=purposes,
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
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    if wallet.fullbalance > 0:
        return redirect(
            url_for("wallets_endpoint.tx_history", wallet_alias=wallet_alias)
        )
    else:
        return redirect(url_for("wallets_endpoint.receive", wallet_alias=wallet_alias))


###### Wallet transaction history ######


@wallets_endpoint.route("/wallet/<wallet_alias>/tx/")
@login_required
def tx(wallet_alias):
    return redirect(url_for("wallets_endpoint.tx_history", wallet_alias=wallet_alias))


@wallets_endpoint.route("/wallet/<wallet_alias>/tx/history/")
@login_required
def tx_history(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet_tx: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    # update balances in the wallet
    wallet.get_balance()
    idx = int(request.args.get("idx", default=0))

    return render_template(
        "wallet/history/txs/wallet_tx.jinja",
        idx=idx,
        wallet_alias=wallet_alias,
        wallet=wallet,
        history=True,
        specter=app.specter,
        rand=rand,
    )


@wallets_endpoint.route("/wallet/<wallet_alias>/tx/utxo/", methods=["GET", "POST"])
@login_required
def tx_utxo(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet_addresses: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    # update balances in the wallet
    wallet.get_balance()
    # check utxo list
    wallet.check_utxo()
    viewtype = "address" if request.args.get("view") != "label" else "label"
    idx = int(request.args.get("idx", default=0))
    if request.method == "POST":
        action = request.form["action"]
        if action == "updatelabel":
            label = request.form["label"]
            account = request.form["account"]
            if viewtype == "address":
                wallet.setlabel(account, label)
            else:
                for address in wallet.addresses_on_label(account):
                    wallet.setlabel(address, label)
                wallet.getdata()
    return render_template(
        "wallet/history/utxo/wallet_utxo.jinja",
        idx=idx,
        wallet_alias=wallet_alias,
        wallet=wallet,
        history=False,
        viewtype=viewtype,
        specter=app.specter,
        rand=rand,
    )


###### Wallet receive ######


@wallets_endpoint.route("/wallet/<wallet_alias>/receive/", methods=["GET", "POST"])
@login_required
def receive(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet_receive: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
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
    history_idx = int(request.args.get("history_idx", default=0))
    past_addresses = wallet.addresses[
        -10 * history_idx - 2 : -10 * (history_idx + 1) - 2 : -1
    ]
    return render_template(
        "wallet/receive/wallet_receive.jinja",
        wallet_alias=wallet_alias,
        wallet=wallet,
        past_addresses=past_addresses,
        past_descriptors=[
            wallet.get_descriptor(address=addr) for addr in past_addresses
        ],
        addresses_count=len(wallet.addresses),
        history_idx=history_idx,
        specter=app.specter,
        rand=rand,
    )


###### Wallet send ######


@wallets_endpoint.route("/wallet/<wallet_alias>/send")
@login_required
def send(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet_send: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    if len(wallet.pending_psbts) > 0:
        return redirect(
            url_for("wallets_endpoint.send_pending", wallet_alias=wallet_alias)
        )
    else:
        return redirect(url_for("wallets_endpoint.send_new", wallet_alias=wallet_alias))


@wallets_endpoint.route("/wallet/<wallet_alias>/send/new", methods=["GET", "POST"])
@login_required
def send_new(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet_send: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    # update balances in the wallet
    wallet.get_balance()
    # update utxo list for coin selection
    wallet.check_utxo()
    psbt = None
    addresses = [""]
    labels = [""]
    amounts = [0]
    fee_rate = 0.0
    err = None
    ui_option = "ui"
    recipients_txt = ""
    if request.method == "POST":
        action = request.form["action"]
        if action == "createpsbt":
            i = 0
            addresses = []
            labels = []
            amounts = []
            ui_option = request.form.get("ui_option")
            if "ui" in ui_option:
                while "address_{}".format(i) in request.form:
                    addresses.append(request.form["address_{}".format(i)])
                    amounts.append(float(request.form["btc_amount_{}".format(i)]))
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
            subtract = bool(request.form.get("subtract", False))
            subtract_from = int(request.form.get("subtract_from", 1)) - 1
            rbf = bool(request.form.get("rbf", False))
            selected_coins = request.form.getlist("coinselect")
            app.logger.info("selected coins: {}".format(selected_coins))
            if "dynamic" in request.form.get("fee_options"):
                fee_rate = float(request.form.get("fee_rate_dynamic"))
            else:
                if request.form.get("fee_rate"):
                    fee_rate = float(request.form.get("fee_rate"))
            try:
                psbt = wallet.createpsbt(
                    addresses,
                    amounts,
                    subtract=subtract,
                    subtract_from=subtract_from,
                    fee_rate=fee_rate,
                    selected_coins=selected_coins,
                    readonly="estimate_fee" in request.form,
                    rbf=rbf,
                )
                if psbt is None:
                    err = "Probably you don't have enough funds, or something else..."
                else:
                    # calculate new amount if we need to subtract
                    if subtract:
                        for v in psbt["tx"]["vout"]:
                            if addresses[0] in v["scriptPubKey"]["addresses"]:
                                amounts[0] = v["value"]
            except Exception as e:
                err = e
                app.logger.error(e)
            if err is None:
                if "estimate_fee" in request.form:
                    return psbt
                return render_template(
                    "wallet/send/sign/wallet_send_sign_psbt.jinja",
                    psbt=psbt,
                    labels=labels,
                    wallet_alias=wallet_alias,
                    wallet=wallet,
                    specter=app.specter,
                    rand=rand,
                )
        elif action == "importpsbt":
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
                labels=labels,
                wallet_alias=wallet_alias,
                wallet=wallet,
                specter=app.specter,
                rand=rand,
            )
        elif action == "openpsbt":
            psbt = ast.literal_eval(request.form["pending_psbt"])
            return render_template(
                "wallet/send/sign/wallet_send_sign_psbt.jinja",
                psbt=psbt,
                labels=labels,
                wallet_alias=wallet_alias,
                wallet=wallet,
                specter=app.specter,
                rand=rand,
            )
        elif action == "deletepsbt":
            try:
                wallet.delete_pending_psbt(
                    ast.literal_eval(request.form["pending_psbt"])["tx"]["txid"]
                )
            except Exception as e:
                flash("Could not delete Pending PSBT!", "error")
        elif action == "rbf":
            try:
                rbf_tx_id = request.form["rbf_tx_id"]
                rbf_fee_rate = float(request.form["rbf_fee_rate"])
                psbt = wallet.send_rbf_tx(rbf_tx_id, rbf_fee_rate)
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
        elif action == "signhotwallet":
            passphrase = request.form["passphrase"]
            psbt = ast.literal_eval(request.form["psbt"])
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
    return render_template(
        "wallet/send/new/wallet_send.jinja",
        psbt=psbt,
        ui_option=ui_option,
        recipients_txt=recipients_txt,
        labels=labels,
        wallet_alias=wallet_alias,
        wallet=wallet,
        specter=app.specter,
        rand=rand,
        error=err,
    )


@wallets_endpoint.route("/wallet/<wallet_alias>/send/pending/", methods=["GET", "POST"])
@login_required
def send_pending(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet_sendpending: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    if request.method == "POST":
        action = request.form["action"]
        if action == "deletepsbt":
            try:
                wallet.delete_pending_psbt(
                    ast.literal_eval(request.form["pending_psbt"])["tx"]["txid"]
                )
            except Exception as e:
                app.logger.error("Could not delete Pending PSBT: %s" % e)
                flash("Could not delete Pending PSBT!", "error")
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


@wallets_endpoint.route("/wallet/<wallet_alias>/send/import")
@login_required
def import_psbt(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet_send: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    err = None
    return render_template(
        "wallet/send/import/wallet_importpsbt.jinja",
        wallet_alias=wallet_alias,
        wallet=wallet,
        specter=app.specter,
        rand=rand,
        error=err,
    )


###### Wallet settings ######


@wallets_endpoint.route("/wallet/<wallet_alias>/settings/", methods=["GET", "POST"])
@login_required
def settings(wallet_alias):
    error = None
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet_receive: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    if request.method == "POST":
        action = request.form["action"]
        if action == "rescanblockchain":
            startblock = int(request.form["startblock"])
            try:
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
                explorer = app.specter.get_default_explorer()
            wallet.rescanutxo(explorer)
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
    else:
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


@wallets_endpoint.route("/wallet/<wallet_alias>/combine/", methods=["POST"])
@login_required
def combine(wallet_alias):
    # only post requests
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while combine: %s" % se)
        return "SpecterError while combine: %s" % se, 500
    # FIXME: ugly...
    txid = request.form.get("txid")
    psbts = [request.form.get("psbt0").strip(), request.form.get("psbt1").strip()]
    raw = {}
    combined = None

    for i, psbt in enumerate(psbts):
        if "UR:BYTES/" in psbt.upper():
            psbt = bcur2base64(psbt).decode()

        # if electrum then it's base43
        try:
            decoded = b43_decode(psbt)
            if decoded.startswith(b"psbt\xff"):
                psbt = b2a_base64(decoded).decode()
            else:
                psbt = decoded.hex()
        except:
            pass

        psbts[i] = psbt
        # psbt should start with cHNi
        # if not - maybe finalized hex tx
        if not psbt.startswith("cHNi"):
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
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while broadcast: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
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


@wallets_endpoint.route("/wallet/<wallet_alias>/decoderawtx/", methods=["GET", "POST"])
@login_required
def decoderawtx(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
        txid = request.form.get("txid", "")
        if txid:
            tx = wallet.rpc.gettransaction(txid)
            return {"success": True, "tx": tx, "rawtx": decoderawtransaction(tx["hex"])}
    except Exception as e:
        app.logger.warning("Failed to fetch transaction data. Exception: {}".format(e))
    return {"success": False}


@wallets_endpoint.route(
    "/wallet/<wallet_alias>/rescan_progress", methods=["GET", "POST"]
)
@login_required
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

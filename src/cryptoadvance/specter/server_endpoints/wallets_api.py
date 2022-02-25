import csv
import json
import logging
import time
from binascii import b2a_base64
from datetime import datetime
from io import StringIO
from math import isnan
from numbers import Number

import requests
from cryptoadvance.specter.util.psbt_creator import PsbtCreator
from flask import Blueprint
from flask import current_app as app
from flask import flash, jsonify, redirect, request, url_for
from flask_babel import lazy_gettext as _
from flask_login import current_user, login_required
from werkzeug.wrappers import Response

from ..helpers import bcur2base64, generate_mnemonic
from ..rpc import RpcError
from ..server_endpoints.filters import assetlabel
from ..specter_error import SpecterError, handle_exception
from ..util.base43 import b43_decode
from ..util.descriptor import Descriptor
from ..util.fee_estimation import FeeEstimationResultEncoder, get_fees
from ..util.price_providers import get_price_at
from ..util.tx import decoderawtransaction

logger = logging.getLogger(__name__)

wallets_endpoint_api = Blueprint("wallets_endpoint_api", __name__)


@wallets_endpoint_api.route("/wallets_loading/", methods=["GET", "POST"])
@login_required
def wallets_loading():
    return {
        "is_loading": app.specter.wallet_manager.is_loading,
        "loaded_wallets": [
            app.specter.wallet_manager.wallets[wallet].alias
            for wallet in app.specter.wallet_manager.wallets
        ],
        "failed_load_wallets": [
            wallet["alias"] for wallet in app.specter.wallet_manager.failed_load_wallets
        ],
    }


@wallets_endpoint_api.route("/generatemnemonic/", methods=["GET", "POST"])
@login_required
def generatemnemonic():
    return {
        "mnemonic": generate_mnemonic(
            strength=int(request.form["strength"]),
            language_code=app.get_language_code(),
        )
    }


@wallets_endpoint_api.route("/get_txout_set_info")
@login_required
@app.csrf.exempt
def txout_set_info():
    res = app.specter.rpc.gettxoutsetinfo()
    return res


@wallets_endpoint_api.route("/get_scantxoutset_status")
@login_required
@app.csrf.exempt
def get_scantxoutset_status():
    status = app.specter.rpc.scantxoutset("status", [])
    app.specter.info["utxorescan"] = status.get("progress", None) if status else None
    if app.specter.info["utxorescan"] is None:
        app.specter.utxorescanwallet = None
    return {
        "active": app.specter.info["utxorescan"] is not None,
        "progress": app.specter.info["utxorescan"],
    }


@wallets_endpoint_api.route("/fees", methods=["GET"])
@login_required
def fees():
    return json.dumps(get_fees(app.specter, app.config), cls=FeeEstimationResultEncoder)


@app.route("/get_fee/<blocks>")
@login_required
def fees_old(blocks):
    """Is this endpoint even used? It has been migrated from controller.py and renamed to fees_old"""
    return app.specter.estimatesmartfee(int(blocks))


@wallets_endpoint_api.route("/wallet/<wallet_alias>/combine/", methods=["POST"])
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
            return _("Cannot parse empty data as PSBT"), 500
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
                return _("Invalid transaction format"), 500

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
        handle_exception(e)
        return _("Unknown error: {}").format(e), 500
    return json.dumps(raw)


@wallets_endpoint_api.route("/wallet/<wallet_alias>/broadcast/", methods=["POST"])
@login_required
def broadcast(wallet_alias):
    wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    tx = request.form.get("tx")
    res = wallet.rpc.testmempoolaccept([tx])[0]
    if res["allowed"]:
        app.specter.broadcast(tx)
        wallet.delete_spent_pending_psbts([tx])
        return jsonify(success=True)
    else:
        return jsonify(
            success=False,
            error=_(
                "Failed to broadcast transaction: transaction is invalid\n{}"
            ).format(res["reject-reason"]),
        )


@wallets_endpoint_api.route(
    "/wallet/<wallet_alias>/broadcast_blockexplorer/", methods=["POST"]
)
@login_required
def broadcast_blockexplorer(wallet_alias):
    wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
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
                    error=_("Failed to broadcast transaction. Network not supported."),
                )
            if explorer == "mempool":
                explorer = f"MEMPOOL_SPACE{'_ONION' if use_tor else ''}"
            elif explorer == "blockstream":
                explorer = f"BLOCKSTREAM_INFO{'_ONION' if use_tor else ''}"
            else:
                return jsonify(
                    success=False,
                    error=_(
                        "Failed to broadcast transaction. Block explorer not supported."
                    ),
                )
            requests_session = app.specter.requests_session(force_tor=use_tor)
            requests_session.post(
                f"{app.config['EXPLORERS_LIST'][explorer]['url']}{url_network}api/tx",
                data=tx,
            )
            wallet.delete_spent_pending_psbts([tx])
            return jsonify(success=True)
        except Exception as e:
            handle_exception(e)
            return jsonify(
                success=False,
                error=_("Failed to broadcast transaction with error: {}").format(e),
            )
    else:
        return jsonify(
            success=False,
            error=_(
                "Failed to broadcast transaction: transaction is invalid\n{}"
            ).format(res["reject-reason"]),
        )


@wallets_endpoint_api.route(
    "/wallet/<wallet_alias>/decoderawtx/", methods=["GET", "POST"]
)
@login_required
@app.csrf.exempt
def decoderawtx(wallet_alias):
    try:
        wallet: Wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
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

                # Enrich utxo data with address_info if the addr is from our Wallet
                for utxo in rawtx.get("vout", []):
                    address = utxo.get("address")
                    addr_obj = wallet.get_address_info(address)
                    if addr_obj:
                        utxo.update(addr_obj)
                        if not utxo.get("label"):
                            utxo["label"] = addr_obj.label

                # TODO: Fetch the relevant Input utxo details so the JS doesn't have to
                #   make a separate call.
            except:
                rawtx = wallet.rpc.decoderawtransaction(tx["hex"])
            # add assets
            if app.specter.is_liquid:
                for v in rawtx["vin"] + rawtx["vout"]:
                    if "asset" in v:
                        v["assetlabel"] = app.specter.asset_label(v["asset"])

            return jsonify(
                success=True,
                tx=tx,
                rawtx=rawtx,
                walletName=wallet.name,
            )
    except RpcError as e:
        if "Invalid or non-wallet transaction id" in str(e):
            # Expected failure when looking up a txid that didn't originate from the
            #   user's Wallet.
            pass
        else:
            app.logger.warning(
                "Failed to fetch transaction data. Exception: {}".format(e)
            )
    except Exception as e:
        app.logger.warning("Failed to fetch transaction data. Exception: {}".format(e))

    return jsonify(success=False)


@wallets_endpoint_api.route(
    "/wallet/<wallet_alias>/rescan_progress", methods=["GET", "POST"]
)
@login_required
@app.csrf.exempt
def rescan_progress(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
        wallet.get_info()
        return jsonify(
            active=wallet.rescan_progress is not None,
            progress=wallet.rescan_progress,
        )
    except SpecterError as se:
        app.logger.error("SpecterError while get wallet rescan_progress: %s" % se)
        return {}


@wallets_endpoint_api.route("/wallet/<wallet_alias>/get_label", methods=["POST"])
@login_required
def get_label(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
        address = request.form.get("address", "")
        label = wallet.getlabel(address)
        return jsonify(
            address=address,
            label=label,
        )
    except Exception as e:
        handle_exception(e)
        return jsonify(
            success=False,
            error=_("Exception trying to get address label: Error: {}").format(e),
        )


@wallets_endpoint_api.route("/wallet/<wallet_alias>/set_label", methods=["POST"])
@login_required
def set_label(wallet_alias):

    wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    address = request.form["address"]
    label = request.form["label"].rstrip()
    wallet.setlabel(address, label)
    return jsonify(success=True)


@wallets_endpoint_api.route("/wallet/<wallet_alias>/txlist", methods=["POST"])
@login_required
@app.csrf.exempt
def txlist(wallet_alias):
    wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    idx = int(request.form.get("idx", 0))
    limit = int(request.form.get("limit", 100))
    search = request.form.get("search", None)
    sortby = request.form.get("sortby", None)
    sortdir = request.form.get("sortdir", "asc")
    service_id = request.form.get("service_id", None)
    fetch_transactions = request.form.get("fetch_transactions", False)
    txlist = wallet.txlist(
        fetch_transactions=fetch_transactions,
        validate_merkle_proofs=app.specter.config.get("validate_merkle_proofs", False),
        current_blockheight=app.specter.info["blocks"],
        service_id=service_id,
    )
    return process_txlist(
        txlist, idx=idx, limit=limit, search=search, sortby=sortby, sortdir=sortdir
    )


@wallets_endpoint_api.route("/wallet/<wallet_alias>/utxo_list", methods=["POST"])
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


@wallets_endpoint_api.route("/wallets_overview/txlist", methods=["POST"])
@login_required
@app.csrf.exempt
def wallets_overview_txlist():
    idx = int(request.form.get("idx", 0))
    limit = int(request.form.get("limit", 100))
    search = request.form.get("search", None)
    sortby = request.form.get("sortby", None)
    sortdir = request.form.get("sortdir", "asc")
    fetch_transactions = request.form.get("fetch_transactions", False)
    service_id = request.form.get("service_id")
    txlist = app.specter.wallet_manager.full_txlist(
        fetch_transactions=fetch_transactions,
        validate_merkle_proofs=app.specter.config.get("validate_merkle_proofs", False),
        current_blockheight=app.specter.info.get("blocks"),
        service_id=service_id,
    )

    return process_txlist(
        txlist, idx=idx, limit=limit, search=search, sortby=sortby, sortdir=sortdir
    )


@wallets_endpoint_api.route("/wallets_overview/utxo_list", methods=["POST"])
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


@wallets_endpoint_api.route("/wallet/<wallet_alias>/addresses_list/", methods=["POST"])
@login_required
@app.csrf.exempt
def addresses_list(wallet_alias):
    """Return a JSON with keys:
        addressesList: list of addresses with the properties
                       (index, address, label, used, utxo, amount, service_id)
        pageCount: total number of pages
    POST parameters:
        idx: pagination index (current page)
        limit: maximum number of items on the page
        sortby: field by which the list will be ordered
                (index, address, label, used, utxo, amount)
        sortdir: 'asc' (ascending) or 'desc' (descending) order
        addressType: the current tab address type ('receive' or 'change')"""
    wallet: Wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)

    idx = int(request.form.get("idx", 0))
    limit = int(request.form.get("limit", 100))
    sortby = request.form.get("sortby", None)
    sortdir = request.form.get("sortdir", "asc")
    address_type = request.form.get("addressType", "receive")

    addresses_list = wallet.addresses_info(address_type == "change")

    result = process_addresses_list(
        addresses_list, idx=idx, limit=limit, sortby=sortby, sortdir=sortdir
    )

    return jsonify(
        addressesList=json.dumps(result["addressesList"]),
        pageCount=result["pageCount"],
    )


@wallets_endpoint_api.route("/wallet/<wallet_alias>/addressinfo/", methods=["POST"])
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
                "isMine": address_info and not address_info.is_external,
                **address_info,
            }
    except Exception as e:
        handle_exception(e)
    return jsonify(success=False)


################## Wallet CSV export data endpoints #######################
# Export wallet addresses list
@wallets_endpoint_api.route("/wallet/<wallet_alias>/addresses_list.csv")
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
        handle_exception(e)
        flash(_("Failed to export addresses list. Error: {}").format(e), "error")
        return redirect(url_for("index"))


# Export wallet transaction history
@wallets_endpoint_api.route("/wallet/<wallet_alias>/transactions.csv")
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
@wallets_endpoint_api.route("/wallet/<wallet_alias>/utxo.csv")
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
        handle_exception(e)
        return _("Failed to export wallet utxo. Error: {}").format(e), 500


@wallets_endpoint_api.route("/wallet/<wallet_alias>/send/estimatefee", methods=["POST"])
@login_required
def estimate_fee(wallet_alias):
    """Returns a json-representation of a psbt which did not get persisted. Kind of a draft-run."""
    wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    # update balances in the wallet
    wallet.update_balance()
    # update utxo list for coin selection
    wallet.check_utxo()
    if request.form.get("estimate_fee") != "true":
        # Very critical as this form-value will prevent persisting the PSBT
        return jsonify(
            success=False,
            error="Your Form did not specify estimate_fee = false. This call is not allowed",
        )
    psbt_creator = PsbtCreator(
        app.specter,
        wallet,
        request.form.get("ui_option", "ui"),
        request_form=request.form,
        recipients_txt=request.form["recipients"],
        recipients_amount_unit=request.form.get("amount_unit_text"),
    )
    try:
        # Won't get persisted
        psbt = psbt_creator.create_psbt(wallet)
        return jsonify(success=True, psbt=psbt)
    except SpecterError as se:
        app.logger.error(se)
        return jsonify(success=False, error=str(se))


@wallets_endpoint_api.route("/wallet/<wallet_alias>/asset_balances")
@login_required
def asset_balances(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
        if app.specter.is_testnet:
            label = "tBTC"
        elif app.specter.is_liquid:
            label = "LBTC"
        else:
            label = "BTC"

        amounts = []
        textUnit = app.specter.unit
        asset_balances = {
            "btc": {
                "balance": wallet.full_available_balance,
                "label": label,
            },
            "sat": {
                "balance": int(wallet.full_available_balance * 1e8),
                "label": "sat",
            },
        }
        for asset in wallet.balance.get("assets", {}).keys():
            asset_balances["asset"] = {
                "balance": wallet.balance.get("assets", {})
                .get(asset, {})
                .get("trusted", 0),
                "label": assetlabel(None, asset),
            }
        return asset_balances
    except Exception as e:
        handle_exception(e)
        return _("Failed to list asses_balances. Error: {}").format(e), 500


# Export all wallets transaction history combined
@wallets_endpoint_api.route("/wallets_overview/full_transactions.csv")
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
        handle_exception(e)
        return _("Failed to export wallets overview history. Error: {}").format(e), 500


# Export all wallets transaction history combined
@wallets_endpoint_api.route("/wallets_overview/full_utxo.csv")
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
        handle_exception(e)
        return _("Failed to export wallets overview utxo. Error: {}").format(e), 500


################## Helpers #######################

# Transactions list to user-friendly CSV format
def txlist_to_csv(wallet, _txlist, specter, current_user, includePricesHistory=False):
    # Why is this line needed?
    # Please remover if you can!
    from flask_babel import lazy_gettext as _

    txlist = []
    for tx in _txlist:
        if isinstance(tx["address"], list):
            tx = tx.copy()
            for i in range(0, len(tx["address"])):
                tx["address"] = tx["address"][i]
                tx["amount"] = tx["amount"][i]
                txlist.append(tx.copy())
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
        _("Date"),
        _("Label"),
        _("Category"),
        _("Amount ({})").format(specter.unit.upper()),
        _("Value ({})").format(symbol),
        _("Rate (BTC/{})").format(symbol)
        if specter.unit != "sat"
        else _("Rate ({}/SAT)").format(symbol),
        _("TxID"),
        _("Address"),
        _("Block Height"),
        _("Timestamp"),
    )
    if not wallet:
        row = (_("Wallet"),) + row
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
        if not tx.get("blockheight", None):
            if tx_raw.get("blockheight", None):
                tx["blockheight"] = tx_raw["blockheight"]
            else:
                tx["blockheight"] = "Unconfirmed"
        if specter.unit == "sat":
            value = float(tx["amount"])
            tx["amount"] = round(value * 1e8)
        amount_price = "not supported"
        rate = "not supported"
        if tx["blocktime"]:
            timestamp = tx["blocktime"]
        else:
            timestamp = tx["time"]
        if includePricesHistory:
            try:
                rate, _ = get_price_at(specter, current_user, timestamp)
                rate = float(rate)
                if specter.unit == "sat":
                    rate = rate / 1e8
                amount_price = float(tx["amount"]) * rate
                amount_price = round(amount_price * 100) / 100
                if specter.unit == "sat":
                    rate = round(1 / rate)
            except SpecterError as se:
                logger.error(se)
                success = False
                rate = "-"

        row = (
            time.strftime("%Y-%m-%d", time.localtime(timestamp)),
            label,
            tx["category"],
            round(tx["amount"], (0 if specter.unit == "sat" else 8)),
            amount_price,
            rate,
            tx["txid"],
            tx["address"],
            tx["blockheight"],
            time,
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
        _("Address"),
        _("Label"),
        _("Index"),
        _("Used"),
        _("Current balance"),
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
            _("(external)")
            if address_info.is_external
            else (
                str(address_info.index)
                + (_(" (change)") if address_info.change else "")
            ),
            address_info.used,
        )
        if address_info.is_external:
            balance_on_address = _("unknown (external address)")
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
        _("Index"),
        _("Address"),
        _("Type"),
        _("Label"),
        _("Used"),
        _("UTXO"),
        _("Amount (BTC)"),
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
    """Prepares the txlist for the ui filtering it with the search-criterias and sorting it"""
    if search:
        search_lower = search.lower()
        txlist = [
            tx
            for tx in txlist
            if search_lower in tx["txid"]
            or (
                any(search in address for address in tx["address"])
                if isinstance(tx["address"], list)
                else search in tx["address"]
            )
            or (
                any(search_lower in label.lower() for label in tx.get("label", ""))
                if isinstance(tx.get("label", ""), list)
                else search_lower in tx.get("label", "").lower()
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
            or (
                float(search.split(" ")[1]) > tx["amount"]
                if search.split(" ")[0] == "<"
                else False
            )
            or (
                float(search.split(" ")[1]) < tx["amount"]
                if search.split(" ")[0] == ">"
                else False
            )
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
    # add assets
    if app.specter.is_liquid:
        for tx in txlist:
            if "asset" in tx:
                if isinstance(tx["asset"], list):
                    tx["assetlabel"] = [
                        app.specter.asset_label(asset) for asset in tx["asset"]
                    ]
                else:
                    tx["assetlabel"] = app.specter.asset_label(tx["asset"])
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

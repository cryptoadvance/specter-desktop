import copy, random

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
from flask_login import login_required, current_user
from flask import current_app as app
from mnemonic import Mnemonic
from ..helpers import is_testnet, generate_mnemonic
from ..key import Key
from ..wallet_manager import purposes

rand = random.randint(0, 1e32)  # to force style refresh

# Setup endpoint blueprint
devices_endpoint = Blueprint("devices_endpoint", __name__)


################## New device #######################

# New device
@devices_endpoint.route("/new_device/", methods=["GET", "POST"])
@login_required
def new_device():
    err = None
    strength = 128
    mnemonic = generate_mnemonic(strength=strength)
    if request.method == "POST":
        if request.form.get("existing_device"):
            device = app.specter.device_manager.get_by_alias(
                request.form.get("existing_device")
            )
            device_type = device.device_type
        else:
            device_type = request.form.get("devices")
            device_name = request.form.get("device_name", "")
            if not device_name:
                err = "Device name must not be empty"
            elif device_name in app.specter.device_manager.devices_names:
                err = "Device with this name already exists"
        xpubs_rows_count = int(request.form["xpubs_rows_count"]) + 1
        if device_type != "bitcoincore":
            keys = []
            for i in range(0, xpubs_rows_count):
                purpose = request.form.get(
                    "xpubs-table-row-{}-purpose".format(i), "Custom"
                )
                xpub = request.form.get("xpubs-table-row-{}-xpub-hidden".format(i), "-")
                if xpub != "-":
                    try:
                        keys.append(Key.parse_xpub(xpub, purpose=purpose))
                    except:
                        err = "Failed to parse these xpubs:\n" + "\n".join(xpub)
                        break
            if not keys and not err:
                err = "xpubs name must not be empty"
            if err is None:
                if request.form.get("existing_device"):
                    device.add_keys(keys)
                    flash("{} keys were added successfully".format(len(keys)))
                    return redirect(
                        url_for("devices_endpoint.device", device_alias=device.alias)
                    )
                device = app.specter.device_manager.add_device(
                    name=device_name, device_type=device_type, keys=keys
                )
                flash("{} was added successfully!".format(device_name))
                return redirect(
                    url_for("devices_endpoint.device", device_alias=device.alias)
                    + "?newdevice=true"
                )
            else:
                flash(err, "error")
        else:
            if len(request.form["mnemonic"].split(" ")) not in [12, 15, 18, 21, 24]:
                err = "Invalid mnemonic entered: Must contain either: 12, 15, 18, 21, or 24 words."
            mnemo = Mnemonic("english")
            if not mnemo.check(request.form["mnemonic"]):
                err = "Invalid mnemonic entered."
            range_start = int(request.form["range_start"])
            range_end = int(request.form["range_end"])
            if range_start > range_end:
                err = "Invalid address range selected."
            mnemonic = request.form["mnemonic"]
            paths = []
            keys_purposes = []
            for i in range(0, xpubs_rows_count):
                purpose = request.form.get(
                    "xpubs-table-row-{}-purpose".format(i), "Custom"
                )
                path = request.form.get(
                    "xpubs-table-row-{}-derivation-hidden".format(i), ""
                )
                if path != "":
                    paths.append(path)
                    keys_purposes.append(purpose)
            if not paths:
                err = "No paths were specified, please provide at lease one."
            if err is None:
                passphrase = request.form["passphrase"]
                file_password = request.form["file_password"]
                if request.form.get("existing_device"):
                    device.add_hot_wallet_keys(
                        mnemonic,
                        passphrase,
                        paths,
                        file_password,
                        app.specter.wallet_manager,
                        is_testnet(app.specter.chain),
                        keys_range=[range_start, range_end],
                        keys_purposes=keys_purposes,
                    )
                    flash("{} keys were added successfully".format(len(paths)))
                    return redirect(
                        url_for("devices_endpoint.device", device_alias=device.alias)
                    )
                device = app.specter.device_manager.add_device(
                    name=device_name, device_type=device_type, keys=[]
                )
                device.setup_device(file_password, app.specter.wallet_manager)
                device.add_hot_wallet_keys(
                    mnemonic,
                    passphrase,
                    paths,
                    file_password,
                    app.specter.wallet_manager,
                    is_testnet(app.specter.chain),
                    keys_range=[range_start, range_end],
                    keys_purposes=keys_purposes,
                )
                flash("{} was added successfully!".format(device_name))
                return redirect(
                    url_for("devices_endpoint.device", device_alias=device.alias)
                    + "?newdevice=true"
                )
            else:
                flash(err, "error")
    return render_template(
        "device/new_device.jinja",
        mnemonic=mnemonic,
        strength=strength,
        specter=app.specter,
        rand=rand,
    )


# New device "manual" (deprecated)
@devices_endpoint.route("/new_device_manual/", methods=["GET", "POST"])
@login_required
def new_device_manual():
    err = None
    device_type = ""
    device_name = ""
    xpubs = ""
    strength = 128
    mnemonic = generate_mnemonic(strength=strength)
    if request.method == "POST":
        action = request.form["action"]
        device_type = request.form["device_type"]
        device_name = request.form["device_name"]
        if action == "newcolddevice":
            if not device_name:
                err = "Device name must not be empty"
            elif device_name in app.specter.device_manager.devices_names:
                err = "Device with this name already exists"
            xpubs = request.form["xpubs"]
            if not xpubs:
                err = "xpubs name must not be empty"
            keys, failed = Key.parse_xpubs(xpubs)
            if len(failed) > 0:
                err = "Failed to parse these xpubs:\n" + "\n".join(failed)
            if err is None:
                device = app.specter.device_manager.add_device(
                    name=device_name, device_type=device_type, keys=keys
                )
                return redirect(
                    url_for("devices_endpoint.device", device_alias=device.alias)
                )
        elif action == "newhotdevice":
            if not device_name:
                err = "Device name must not be empty"
            elif device_name in app.specter.device_manager.devices_names:
                err = "Device with this name already exists"
            if len(request.form["mnemonic"].split(" ")) not in [12, 15, 18, 21, 24]:
                err = "Invalid mnemonic entered: Must contain either: 12, 15, 18, 21, or 24 words."
            mnemo = Mnemonic("english")
            if not mnemo.check(request.form["mnemonic"]):
                err = "Invalid mnemonic entered."
            range_start = int(request.form["range_start"])
            range_end = int(request.form["range_end"])
            if range_start > range_end:
                err = "Invalid address range selected."
            if err is None:
                mnemonic = request.form["mnemonic"]
                paths = [
                    l.strip()
                    for l in request.form["derivation_paths"].split("\n")
                    if len(l) > 0
                ]
                passphrase = request.form["passphrase"]
                file_password = request.form["file_password"]
                device = app.specter.device_manager.add_device(
                    name=device_name, device_type=device_type, keys=[]
                )
                device.setup_device(file_password, app.specter.wallet_manager)
                device.add_hot_wallet_keys(
                    mnemonic,
                    passphrase,
                    paths,
                    file_password,
                    app.specter.wallet_manager,
                    is_testnet(app.specter.chain),
                    keys_range=[range_start, range_end],
                )
                return redirect(
                    url_for("devices_endpoint.device", device_alias=device.alias)
                )
        elif action == "generatemnemonic":
            strength = int(request.form["strength"])
            mnemonic = generate_mnemonic(strength=strength)
    return render_template(
        "device/new_device_manual.jinja",
        device_type=device_type,
        device_name=device_name,
        xpubs=xpubs,
        mnemonic=mnemonic,
        strength=strength,
        error=err,
        specter=app.specter,
        rand=rand,
    )


################## Device page #######################


@devices_endpoint.route("device/<device_alias>/", methods=["GET", "POST"])
@login_required
def device(device_alias):
    err = None
    try:
        device = app.specter.device_manager.get_by_alias(device_alias)
    except:
        return render_template(
            "base.jinja", error="Device not found", specter=app.specter, rand=rand
        )
    if not device:
        return redirect(url_for("index"))
    wallets = device.wallets(app.specter.wallet_manager)
    if request.method == "POST":
        action = request.form["action"]
        if action == "forget":
            if len(wallets) != 0:
                err = "Device could not be removed since it is used in wallets: {}.<br>You must delete those wallets before you can remove this device.<br>You can delete a wallet from its Settings -> Advanced page.".format(
                    [wallet.name for wallet in wallets]
                )
            else:
                app.specter.device_manager.remove_device(
                    device,
                    app.specter.wallet_manager,
                    bitcoin_datadir=app.specter.bitcoin_datadir,
                    chain=app.specter.chain,
                )
                return redirect("")
        elif action == "delete_key":
            key = Key.from_json({"original": request.form["key"]})
            wallets_with_key = [w for w in wallets if key in w.keys]
            if len(wallets_with_key) != 0:
                err = "Key could not be removed since it is used in wallets: {}.<br>You must delete those wallets before you can remove this key.<br>You can delete a wallet from its Settings -> Advanced page.".format(
                    ", ".join([wallet.name for wallet in wallets_with_key])
                )
            else:
                device.remove_key(key)
        elif action == "rename":
            device_name = request.form["newtitle"]
            if not device_name:
                flash("Device name must not be empty", "error")
            elif device_name == device.name:
                pass
            elif device_name in app.specter.device_manager.devices_names:
                flash("Device already exists", "error")
            else:
                device.rename(device_name)
        elif action == "add_keys":
            strength = 128
            mnemonic = generate_mnemonic(strength=strength)
            return render_template(
                "device/new_device.jinja",
                mnemonic=mnemonic,
                strength=strength,
                existing_device=device,
                device_alias=device_alias,
                specter=app.specter,
                rand=rand,
            )
        elif action == "morekeys":
            if device.hot_wallet:
                if len(request.form["mnemonic"].split(" ")) not in [12, 15, 18, 21, 24]:
                    err = "Invalid mnemonic entered: Must contain either: 12, 15, 18, 21, or 24 words."
                mnemo = Mnemonic("english")
                if not mnemo.check(request.form["mnemonic"]):
                    err = "Invalid mnemonic entered."
                range_start = int(request.form["range_start"])
                range_end = int(request.form["range_end"])
                if range_start > range_end:
                    err = "Invalid address range selected."
                if err is None:
                    mnemonic = request.form["mnemonic"]
                    paths = [
                        l.strip()
                        for l in request.form["derivation_paths"].split("\n")
                        if len(l) > 0
                    ]
                    passphrase = request.form["passphrase"]
                    file_password = request.form["file_password"]
                    device.add_hot_wallet_keys(
                        mnemonic,
                        passphrase,
                        paths,
                        file_password,
                        app.specter.wallet_manager,
                        is_testnet(app.specter.chain),
                        keys_range=[range_start, range_end],
                    )
            else:
                # refactor to fn
                xpubs = request.form["xpubs"]
                keys, failed = Key.parse_xpubs(xpubs)
                err = None
                if len(failed) > 0:
                    err = "Failed to parse these xpubs:\n" + "\n".join(failed)
                    return render_template(
                        "device/new_device_manual.jinja",
                        device=device,
                        device_alias=device_alias,
                        xpubs=xpubs,
                        error=err,
                        specter=app.specter,
                        rand=rand,
                    )
                if err is None:
                    device.add_keys(keys)
        elif action == "settype":
            device_type = request.form["device_type"]
            device.set_type(device_type)
    device = copy.deepcopy(device)
    device.keys.sort(
        key=lambda k: k.metadata["chain"] + k.metadata["purpose"], reverse=True
    )
    return render_template(
        "device/device.jinja",
        device=device,
        device_alias=device_alias,
        purposes=purposes,
        wallets=wallets,
        error=err,
        specter=app.specter,
        rand=rand,
    )

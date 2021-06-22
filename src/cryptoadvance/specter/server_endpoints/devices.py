import copy, random, json, re

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
from flask import current_app as app
from flask_babel import lazy_gettext as _
from flask_login import login_required, current_user
from mnemonic import Mnemonic
from ..devices.bitcoin_core import BitcoinCore
from ..helpers import is_testnet, generate_mnemonic, validate_mnemonic
from ..key import Key
from ..managers.device_manager import get_device_class
from ..managers.wallet_manager import purposes
from ..specter_error import handle_exception

rand = random.randint(0, 1e32)  # to force style refresh

# Setup endpoint blueprint
devices_endpoint = Blueprint("devices_endpoint", __name__)


################## New device #######################
# New device type
@devices_endpoint.route("/new_device_type/", methods=["GET", "POST"])
@login_required
def new_device_type():
    return render_template(
        "device/new_device/new_device_type.jinja",
        specter=app.specter,
        rand=rand,
    )


@devices_endpoint.route("/new_device_keys/<device_type>/", methods=["GET", "POST"])
@login_required
def new_device_keys(device_type):
    err = None
    mnemonic = ""
    passphrase = ""
    file_password = ""
    range_start = 0
    range_end = 1000
    existing_device = None
    if request.method == "POST":
        mnemonic = request.form.get("mnemonic", "")
        passphrase = request.form.get("passphrase", "")
        file_password = request.form.get("file_password", "")
        range_start = int(request.form.get("range_start", "0"))
        range_end = int(request.form.get("range_end", "1000"))
        existing_device = request.form.get("existing_device", None)
        if existing_device:
            device = app.specter.device_manager.get_by_alias(existing_device)
        else:
            device_name = request.form.get("device_name", "")
            if not device_name:
                err = _("Device name cannot be empty")
            elif device_name in app.specter.device_manager.devices_names:
                err = _("Device with this name already exists")
        xpubs_rows_count = int(request.form["xpubs_rows_count"]) + 1
        keys = []
        paths = []
        keys_purposes = []
        for i in range(0, xpubs_rows_count):
            purpose = request.form.get("xpubs-table-row-{}-purpose".format(i), "Custom")
            xpub = request.form.get("xpubs-table-row-{}-xpub-hidden".format(i), "-")
            path = request.form.get(
                "xpubs-table-row-{}-derivation-hidden".format(i), ""
            )
            if path != "":
                paths.append(path)
                keys_purposes.append(purpose)
            if xpub != "-":
                try:
                    keys.append(Key.parse_xpub(xpub, purpose=purpose))
                except:
                    err = _("Failed to parse these xpubs") + ":\n" + "\n".join(xpub)
                    break
        if not keys and not err:
            if device_type in ["bitcoincore", "elementscore"]:
                if not paths:
                    err = _("No paths were specified, please provide at least one.")
                if err is None:
                    if existing_device:
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
                        flash(_("{} keys were added successfully").format(len(paths)))
                        return redirect(
                            url_for(
                                "devices_endpoint.device", device_alias=device.alias
                            )
                        )
                    device = app.specter.device_manager.add_device(
                        name=device_name, device_type=device_type, keys=[]
                    )
                    try:
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
                        flash(_("{} was added successfully!").format(device_name))
                        return redirect(
                            url_for(
                                "devices_endpoint.device", device_alias=device.alias
                            )
                            + "?newdevice=true"
                        )
                    except Exception as e:
                        handle_exception(e)
                        flash(
                            _("Failed to setup hot wallet. Error: {}").format(e),
                            "error",
                        )
                        app.specter.device_manager.remove_device(
                            device,
                            app.specter.wallet_manager,
                            bitcoin_datadir=app.specter.bitcoin_datadir,
                            chain=app.specter.chain,
                        )
            else:
                err = _("xpubs list must not be empty")
        elif not err:
            if existing_device:
                device.add_keys(keys)
                flash(_("{} keys were added successfully").format(len(keys)))
                return redirect(
                    url_for("devices_endpoint.device", device_alias=device.alias)
                )
            device = app.specter.device_manager.add_device(
                name=device_name, device_type=device_type, keys=keys
            )
            if app.specter.is_liquid:
                return render_template(
                    "device/device_blinding_key.jinja",
                    new_device=True,
                    device=device,
                    error=err,
                    specter=app.specter,
                    rand=rand,
                )
            else:
                flash(_("{} was added successfully!").format(device_name))
                return redirect(
                    url_for("devices_endpoint.device", device_alias=device.alias)
                    + "?newdevice=true"
                )

    return render_template(
        "device/new_device/new_device_keys.jinja",
        device_class=get_device_class(device_type),
        mnemonic=mnemonic,
        passphrase=passphrase,
        file_password=file_password,
        range_start=range_start,
        range_end=range_end,
        existing_device=app.specter.device_manager.get_by_alias(existing_device)
        if existing_device
        else None,
        error=err,
        specter=app.specter,
        rand=rand,
    )


@devices_endpoint.route("/new_device_mnemonic/<device_type>/", methods=["GET", "POST"])
@login_required
def new_device_mnemonic(device_type):
    err = None
    strength = 128
    mnemonic = generate_mnemonic(
        strength=strength, language_code=app.get_language_code()
    )
    existing_device = None
    if request.method == "POST":
        if len(request.form["mnemonic"].split(" ")) not in [12, 15, 18, 21, 24]:
            err = _(
                "Invalid mnemonic entered: Must contain either: 12, 15, 18, 21, or 24 words."
            )
        if not validate_mnemonic(words=request.form["mnemonic"]):
            err = _("Invalid mnemonic entered.")
        range_start = int(request.form["range_start"])
        range_end = int(request.form["range_end"])
        if range_start > range_end:
            err = _("Invalid address range selected.")
        mnemonic = request.form["mnemonic"]
        passphrase = request.form["passphrase"]
        file_password = request.form["file_password"]
        existing_device = request.form.get("existing_device", None)
        if existing_device:
            existing_device = app.specter.device_manager.get_by_alias(existing_device)
        if not err:
            return render_template(
                "device/new_device/new_device_keys.jinja",
                device_class=get_device_class(device_type),
                mnemonic=mnemonic,
                passphrase=passphrase,
                file_password=file_password,
                range_start=range_start,
                range_end=range_end,
                existing_device=existing_device,
                error=err,
                specter=app.specter,
                rand=rand,
            )

    return render_template(
        "device/new_device/new_device_mnemonic.jinja",
        device_type=device_type,
        strength=strength,
        mnemonic=mnemonic,
        existing_device=existing_device,
        error=err,
        specter=app.specter,
        rand=rand,
    )


@devices_endpoint.route("/device_blinding_key/<device_alias>/", methods=["GET", "POST"])
@login_required
def device_blinding_key(device_alias):
    err = None
    try:
        device = app.specter.device_manager.get_by_alias(device_alias)
    except:
        return render_template(
            "base.jinja", error=_("Device not found"), specter=app.specter, rand=rand
        )
    if not device:
        return redirect(url_for("index"))
    if request.method == "POST":
        new_device = request.form.get("new_device", False)
        blinding_key = request.form.get("blinding_key")
        device.set_blinding_key(blinding_key)
        if not new_device:
            flash(_("Master blinding key was added successfully"))
        return redirect(
            url_for("devices_endpoint.device", device_alias=device.alias)
            + ("?newdevice=true" if new_device else "")
        )

    return render_template(
        "device/device_blinding_key.jinja",
        device=device,
        error=err,
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
    mnemonic = generate_mnemonic(
        strength=strength, language_code=app.get_language_code()
    )
    if request.method == "POST":
        action = request.form["action"]
        device_type = request.form["device_type"]
        device_name = request.form["device_name"]
        if action == "newcolddevice":
            if not device_name:
                err = _("Device name cannot be empty")
            elif device_name in app.specter.device_manager.devices_names:
                err = _("Device with this name already exists")
            xpubs = request.form["xpubs"]
            if not xpubs:
                err = _("xpubs name cannot be empty")
            keys, failed = Key.parse_xpubs(xpubs)
            if len(failed) > 0:
                err = _("Failed to parse these xpubs") + ":\n" + "\n".join(failed)
            if err is None:
                device = app.specter.device_manager.add_device(
                    name=device_name, device_type=device_type, keys=keys
                )
                return redirect(
                    url_for("devices_endpoint.device", device_alias=device.alias)
                )
        elif action == "newhotdevice":
            if not device_name:
                err = _("Device name cannot be empty")
            elif device_name in app.specter.device_manager.devices_names:
                err = _("Device with this name already exists")
            if len(request.form["mnemonic"].split(" ")) not in [12, 15, 18, 21, 24]:
                err = _(
                    "Invalid mnemonic entered: Must contain either: 12, 15, 18, 21, or 24 words."
                )

            if not validate_mnemonic(words=request.form["mnemonic"]):
                err = _("Invalid mnemonic entered.")
            range_start = int(request.form["range_start"])
            range_end = int(request.form["range_end"])
            if range_start > range_end:
                err = _("Invalid address range selected.")
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
                try:
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
                except Exception as e:
                    handle_exception(e)
                    flash(_("Failed to setup hot wallet. Error: {}").format(e), "error")
                    app.specter.device_manager.remove_device(
                        device,
                        app.specter.wallet_manager,
                        bitcoin_datadir=app.specter.bitcoin_datadir,
                        chain=app.specter.chain,
                    )
        elif action == "generatemnemonic":
            strength = int(request.form["strength"])
            mnemonic = generate_mnemonic(
                strength=strength, language_code=app.get_language_code()
            )
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
            "base.jinja", error=_("Device not found"), specter=app.specter, rand=rand
        )
    if not device:
        return redirect(url_for("index"))
    wallets = device.wallets(app.specter.wallet_manager)
    if request.method == "POST":
        action = request.form["action"]
        if action == "forget":
            if len(wallets) != 0:
                # TODO: Long message strings like this should be moved into a template.
                err = (
                    _(
                        "Device could not be removed since it is used in wallets: {}"
                    ).format([wallet.name for wallet in wallets])
                    + "<br>"
                    + _(
                        "You must delete those wallets before you can remove this device."
                    )
                    + "<br>"
                    + _("You can delete a wallet from its Settings -> Advanced page.")
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
                # TODO: Long message strings like this should be moved into a template.
                err = (
                    _(
                        "Key could not be removed since it is used in wallets: {}"
                    ).format(", ".join([wallet.name for wallet in wallets_with_key]))
                    + "<br>"
                    + _("You must delete those wallets before you can remove this key.")
                    + "<br>"
                    + _("You can delete a wallet from its Settings -> Advanced page.")
                )
            else:
                device.remove_key(key)
        elif action == "rename":
            device_name = request.form["newtitle"]
            if not device_name:
                flash(_("Device name cannot be empty"), "error")
            elif device_name == device.name:
                pass
            elif device_name in app.specter.device_manager.devices_names:
                flash(_("Device already exists"), "error")
            else:
                device.rename(device_name)
        elif action == "add_keys":
            strength = 128
            mnemonic = generate_mnemonic(
                strength=strength, language_code=app.get_language_code()
            )
            if device.hot_wallet:
                return render_template(
                    "device/new_device/new_device_mnemonic.jinja",
                    mnemonic=mnemonic,
                    strength=strength,
                    existing_device=device,
                    device_alias=device_alias,
                    device_class=get_device_class(device.device_type),
                    specter=app.specter,
                    rand=rand,
                )
            else:
                return render_template(
                    "device/new_device/new_device_keys.jinja",
                    existing_device=device,
                    device_alias=device_alias,
                    device_class=get_device_class(device.device_type),
                    specter=app.specter,
                    rand=rand,
                )
        elif action == "settype":
            device_type = request.form["device_type"]
            device.set_type(device_type)
    device = copy.deepcopy(device)

    def sort_accounts(k):
        # Ordering: 1) chain 2) account 3) purpose
        pattern = r"^m\/([0-9]+)h\/([0-9])h\/([0-9]+)h"
        if not k.derivation:
            return 0
        match = re.search(pattern, k.derivation)
        if not match:
            return 0
        return (
            int(match.group(1))
            + (int(match.group(2)) + 1) * 1000000
            + (int(match.group(3)) + 1) * 2000
        )

    device.keys.sort(key=sort_accounts, reverse=False)
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

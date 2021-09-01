from datetime import datetime
from flask import current_app as app
from flask import Blueprint
from jinja2 import contextfilter
from ..helpers import to_ascii20

filters_bp = Blueprint("filters", __name__)

############### filters ##################


@contextfilter
@filters_bp.app_template_filter("ascii20")
def ascii20(context, name):
    return to_ascii20(name)


@contextfilter
@filters_bp.app_template_filter("datetime")
def timedatetime(context, s):
    return format(datetime.fromtimestamp(s), "%d.%m.%Y %H:%M")


@contextfilter
@filters_bp.app_template_filter("btcamount")
def btcamount(context, value):
    if value < 0:
        return "Confidential"
    value = round(float(value), 8)
    return "{:,.8f}".format(value).rstrip("0").rstrip(".")


@contextfilter
@filters_bp.app_template_filter("btc2sat")
def btc2sat(context, value):
    value = int(round(float(value) * 1e8))
    return f"{value}"


@contextfilter
@filters_bp.app_template_filter("feerate")
def feerate(context, value):
    value = float(value) * 1e8
    # workaround for minimal fee rate
    # because 1.01 doesn't look nice
    if value <= 1.02:
        value = 1
    return "{:,.2f}".format(value).rstrip("0").rstrip(".")


@contextfilter
@filters_bp.app_template_filter("btcunitamount")
def btcunitamount(context, value):
    if app.specter.hide_sensitive_info:
        return "#########"
    if value < 0:
        return "Confidential"
    if app.specter.unit != "sat":
        return btcamount(context, value)
    value = float(value)
    return "{:,.0f}".format(round(value * 1e8))


@contextfilter
@filters_bp.app_template_filter("altunit")
def altunit(context, value):
    if app.specter.hide_sensitive_info:
        return "########"
    if value < 0:
        return "-"
    if app.specter.price_check and (app.specter.alt_rate and app.specter.alt_symbol):
        rate = (
            "{:,.2f}".format(float(value) * float(app.specter.alt_rate))
            .rstrip("0")
            .rstrip(".")
        )
        if app.specter.alt_symbol in ["$", "£"]:
            return app.specter.alt_symbol + rate
        else:
            return rate + app.specter.alt_symbol
    return ""


@contextfilter
@filters_bp.app_template_filter("bytessize")
def bytessize(context, value):
    value = float(value)
    return "{:,.0f}".format(value / float(1 << 30)) + " GB"


@contextfilter
@filters_bp.app_template_filter("assetlabel")
def assetlabel(context, asset):
    if app.specter.hide_sensitive_info:
        return "####"
    return app.specter.asset_label(asset)

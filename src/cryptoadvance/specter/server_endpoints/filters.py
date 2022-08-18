from datetime import datetime
from flask import current_app as app
from flask import Blueprint
from jinja2 import pass_context
from ..helpers import to_ascii20
from ..util.common import satamount_formatted, btcamount_formatted

filters_bp = Blueprint("filters", __name__)

############### filters ##################


@pass_context
@filters_bp.app_template_filter("ascii20")
def ascii20(context, name):
    return to_ascii20(name)


@pass_context
@filters_bp.app_template_filter("unique_len")
def unique_len(context, arr):
    return len(set(arr))


@pass_context
@filters_bp.app_template_filter("datetime")
def timedatetime(context, s):
    return format(datetime.fromtimestamp(s), "%d.%m.%Y %H:%M")


@pass_context
@filters_bp.app_template_filter("average_of_attribute")
def average_of_attribute(context, values, attribute):
    dicts = [
        getattr(value, attribute)
        for value in values
        if getattr(value, attribute) is not None
    ]
    return sum(dicts) / len(dicts) if dicts else None


@pass_context
@filters_bp.app_template_filter("btcunitamount_fixed_decimals")
def btcunitamount_fixed_decimals(
    context,
    value,
    maximum_digits_to_strip=7,
    minimum_digits_to_strip=6,
    enable_digit_spaces_for_counting=True,
):
    if app.specter.hide_sensitive_info:
        return "#########"
    if value is None:
        return "Unknown"
    if value < 0 and app.specter.is_liquid:
        return "Confidential"
    if app.specter.unit == "sat":
        return satamount_formatted(
            value, enable_digit_spaces_for_counting=enable_digit_spaces_for_counting
        )

    return btcamount_formatted(
        value,
        maximum_digits_to_strip=maximum_digits_to_strip,
        minimum_digits_to_strip=minimum_digits_to_strip,
        enable_digit_spaces_for_counting=enable_digit_spaces_for_counting,
    )


@pass_context
@filters_bp.app_template_filter("btcamount")
def btcamount(context, value):
    if value is None:
        return "Unknown"
    if value < 0 and app.specter.is_liquid:
        return "Confidential"
    value = round(float(value), 8)
    return "{:,.8f}".format(value).rstrip("0").rstrip(".")


@pass_context
@filters_bp.app_template_filter("btc2sat")
def btc2sat(context, value):
    value = int(round(float(value) * 1e8))
    return f"{value}"


@pass_context
@filters_bp.app_template_filter("feerate")
def feerate(context, value):
    value = float(value) * 1e8
    # workaround for minimal fee rate
    # because 1.01 doesn't look nice
    if value <= 1.02:
        value = 1
    return "{:,.2f}".format(value).rstrip("0").rstrip(".")


@pass_context
@filters_bp.app_template_filter("btcunitamount")
def btcunitamount(context, value):
    if app.specter.hide_sensitive_info:
        return "#########"
    if value is None:
        return "Unknown"
    if value < 0 and app.specter.is_liquid:
        return "Confidential"
    if app.specter.unit != "sat":
        return btcamount(context, value)
    value = float(value)
    return "{:,.0f}".format(round(value * 1e8))


@pass_context
@filters_bp.app_template_filter("altunit")
def altunit(context, value):
    if app.specter.hide_sensitive_info:
        return "########"
    if value is None:
        return "Can't be calculated"
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


@pass_context
@filters_bp.app_template_filter("bytessize")
def bytessize(context, value):
    value = float(value)
    return "{:,.0f}".format(value / float(1 << 30)) + " GB"


@pass_context
@filters_bp.app_template_filter("assetlabel")
def assetlabel(context, asset):
    if app.specter.hide_sensitive_info:
        return "####"
    return app.specter.asset_label(asset)

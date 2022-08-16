from datetime import datetime
from flask import current_app as app
from flask import Blueprint
from jinja2 import pass_context
from ..helpers import to_ascii20

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
@filters_bp.app_template_filter("any_attribute")
def any_attribute(context, values, attribute=None):
    return any([getattr(value, attribute) for value in values])


@pass_context
@filters_bp.app_template_filter("sum_with_subdicts")
def sum_with_subdicts(context, dicts, attribute=None):
    summed_dict = {}
    for d in dicts:
        for k, v in getattr(d, attribute).items():
            if k not in summed_dict:
                summed_dict[k] = 0
            print(v)
            summed_dict[k] += v
    return summed_dict


@pass_context
@filters_bp.app_template_filter("btcamount_fixed_decimals")
def btcamount_fixed_decimals(context, value):
    if value is None:
        return "Unknown"
    if value < 0 and app.specter.is_liquid:
        return "Confidential"
    value = round(float(value), 8)
    formatted_amount = "{:,.8f}".format(value)

    def replace_substring(text, start_position, length, new_str):
        return text[:start_position] + new_str + text[start_position + length :]

    # strip last digits for better readability and replace with invisible characters
    for i in reversed(range(len(formatted_amount))):
        if formatted_amount[i] == "0":
            # replace with https://unicode-table.com/en/2007/
            formatted_amount = replace_substring(formatted_amount, i, 1, " ")
            continue
        elif formatted_amount[i] == ".":
            # replace with https://unicode-table.com/en/2008/
            formatted_amount = replace_substring(formatted_amount, i, 1, " ")
        break
    return formatted_amount


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

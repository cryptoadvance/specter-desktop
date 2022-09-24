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
@filters_bp.app_template_filter("average_of_attribute")
def average_of_attribute(context, values, attribute):
    dicts = [
        getattr(value, attribute)
        for value in values
        if getattr(value, attribute) is not None
    ]
    return sum(dicts) / len(dicts) if dicts else None


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

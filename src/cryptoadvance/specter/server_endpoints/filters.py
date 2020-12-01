from datetime import datetime
from flask import current_app as app
from ..helpers import to_ascii20

############### filters ##################


@app.template_filter("ascii20")
def ascii20(name):
    return to_ascii20(name)


@app.template_filter("datetime")
def timedatetime(s):
    return format(datetime.fromtimestamp(s), "%d.%m.%Y %H:%M")


@app.template_filter("btcamount")
def btcamount(value):
    value = round(float(value), 8)
    return "{:,.8f}".format(value).rstrip("0").rstrip(".")


@app.template_filter("btc2sat")
def btc2sat(value):
    value = int(round(float(value) * 1e8))
    return f"{value}"


@app.template_filter("feerate")
def feerate(value):
    value = float(value) * 1e8
    # workaround for minimal fee rate
    # because 1.01 doesn't look nice
    if value <= 1.02:
        value = 1
    return "{:,.2f}".format(value).rstrip("0").rstrip(".")


@app.template_filter("btcunitamount")
def btcunitamount(value):
    if app.specter.unit != "sat":
        return btcamount(value)
    value = float(value)
    return "{:,.0f}".format(round(value * 1e8))


@app.template_filter("altunit")
def altunit(value):
    if app.specter.price_check and (app.specter.alt_rate and app.specter.alt_symbol):
        return (
            "{:,.2f}".format(float(value) * float(app.specter.alt_rate))
            .rstrip("0")
            .rstrip(".")
            + app.specter.alt_symbol
        )
    return ""


@app.template_filter("bytessize")
def bytessize(value):
    value = float(value)
    return "{:,.0f}".format(value / float(1 << 30)) + " GB"

"""
Backend Template

Use this to display server debugging info during development

"""
from flask import render_template
from cryptoadvance.specter.api import api_bp


@api_bp.route("/")
def api():
    """rendering the documentation for the api"""
    return render_template("api.html", msg="API Blueprint View")

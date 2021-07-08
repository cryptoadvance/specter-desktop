from flask import render_template
from cryptoadvance.specter.api import api_bp
from flask import current_app as app


@api_bp.route("/")
def api():
    """rendering the documentation for the api"""
    return render_template(
        "api.html", version=app.specter.version.get_current_version()
    )

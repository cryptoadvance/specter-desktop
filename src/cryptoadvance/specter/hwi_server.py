import json, random
from flask import Flask, jsonify, render_template, request
from flask import current_app as app
from flask_login import login_required, login_user, logout_user, current_user
from .hwi_rpc import HWIBridge

rand = random.randint(0, 1e32) # to force style refresh

hwi = HWIBridge()

@app.route("/hwi_rpc/", methods=["POST"])
@login_required
def api():
    """JSON-RPC for ... anything. In this case - HWI Bridge"""
    try:
        data = json.loads(request.data)
    except:
        return jsonify({
            "jsonrpc": "2.0",
            "error": { "code": -32700, "message": "Parse error" },
            "id": None
        }), 500
    return jsonify(hwi.jsonrpc(data))

@app.route('/hwi_new_device/')
@login_required
def hwi_new_device_xpubs():
    app.specter.check()
    return render_template("device/hwi_new_device_xpubs.jinja", specter=app.specter, rand=rand)

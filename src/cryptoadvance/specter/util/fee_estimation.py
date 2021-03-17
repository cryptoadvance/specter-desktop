def get_fees(specter):
    if specter.fee_estimator == "mempool":
        # Try first with Tor hidden service
        try:
            requests_session = specter.requests_session(force_tor=True)
            return requests_session.get(
                "http://mempoolhqx4isw62xs7abwphsq7ldayuidyx2v2oethdhhj6mlo2r6ad.onion/api/v1/fees/recommended"
            ).json()
            return
        except Exception:
            # Try without Tor if failed, or fall back to Bitcoin Core if only Tor is on
            if not specter.only_tor:
                try:
                    requests_session = specter.requests_session(force_tor=False)
                    return requests_session.get(
                        "https://mempool.space/api/v1/fees/recommended"
                    ).json()
                except Exception:
                    pass  # Falling back to Bitcoin Core
    elif specter.fee_estimator == "custom":
        try:
            if specter.config["fee_estimator_custom_url"].endswith("/"):
                custom_url = (
                    specter.config["fee_estimator_custom_url"]
                    + "api/v1/fees/recommended"
                )
            else:
                custom_url = (
                    specter.config["fee_estimator_custom_url"]
                    + "/api/v1/fees/recommended"
                )
            requests_session = specter.requests_session(
                force_tor=".onion/" in custom_url
            )
            return requests_session.get(custom_url).json()
        except Exception:
            pass  # Falling back to Bitcoin Core

    return {
        "fastestFee": int((float(specter.estimatesmartfee(1)["feerate"]) / 1000) * 1e8),
        "halfHourFee": int(
            (float(specter.estimatesmartfee(3)["feerate"]) / 1000) * 1e8
        ),
        "hourFee": int((float(specter.estimatesmartfee(6)["feerate"]) / 1000) * 1e8),
        "minimumFee": int(
            (float(specter.estimatesmartfee(20)["feerate"]) / 1000) * 1e8
        ),
    }

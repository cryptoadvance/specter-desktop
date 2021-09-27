import logging
import re
import requests
import urllib3

logger = logging.getLogger(__name__)


class FeeEstimationResult:
    """A tiny object to pass the Fee Estimation Results around"""

    def __init__(self, result):
        self.result = result
        self._error_message = None

    @property
    def error_message(self):
        return self._error_message

    @error_message.setter
    def error_message(self, value):
        if self._error_message != None:
            self._error_message = self._error_message + " and " + value
        else:
            self._error_message = value

    @property
    def result(self):
        return self._result

    @result.setter
    def result(self, value):
        self._result = value


def get_fees(specter, config):
    try:
        return _get_fees(specter, config)
    except Exception as e:
        fee_estimation = FeeEstimationResult(
            {
                "fastestFee": 1,
                "halfHourFee": 1,
                "hourFee": 1,
                "minimumFee": 1,
            }
        )
        fee_estimation.error_message = f"Failed to Fetch fee estimation. Please use manual fee calculation. Error: {e}"
        return fee_estimation


def _get_fees(specter, config):
    fee_estimation_result = FeeEstimationResult(None)  # Just in case we have errors
    timeout = config["FEEESTIMATION_REQUEST_TIMEOUT"]
    if specter.is_liquid:
        return FeeEstimationResult(
            {
                "fastestFee": 0.1,
                "halfHourFee": 0.1,
                "hourFee": 0.1,
                "minimumFee": 0.1,
            }
        )
    if specter.fee_estimator == "mempool":
        # Try first with Tor hidden service
        try:
            requests_session = specter.requests_session(force_tor=True)
            return FeeEstimationResult(
                requests_session.get(
                    f"{config['EXPLORERS_LIST']['MEMPOOL_SPACE_ONION']['url']}api/v1/fees/recommended",
                    timeout=timeout,
                ).json()
            )
        except (requests.exceptions.Timeout, urllib3.exceptions.ReadTimeoutError) as to:
            # Timeout is effectively one of the two:
            # ConnectTimeout: The request timed out while trying to connect to the remote server
            # ReadTimeout: The server did not send any data in the allotted amount of time.
            # ReadTimeoutError: Raised when a socket timeout occurs while receiving data from a server

            # Try without Tor if failed, or fall back to Bitcoin Core if only Tor is on
            fee_estimation_result.error_message = f"Timeout while fetching fee estimation from mempool.space Tor hidden service (timeout {timeout}). Using Bitcoin Core instead."

            if not specter.only_tor:
                try:
                    requests_session = specter.requests_session(force_tor=False)
                    fee_estimation_result.result = requests_session.get(
                        f"{config['EXPLORERS_LIST']['MEMPOOL_SPACE']['url']}api/v1/fees/recommended",
                        timeout=timeout,
                    ).json()
                    logger.warn(fee_estimation_result.error_message)
                    return fee_estimation_result
                except (
                    requests.exceptions.Timeout,
                    urllib3.exceptions.ReadTimeoutError,
                ) as to:
                    fee_estimation_result.error_message = f"Timeout while fetching estimation from mempool.space (timeout {timeout}). Using Bitcoin Core instead."

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
            fee_estimation_result.result = requests_session.get(
                custom_url, timeout=timeout
            ).json()
            logger.warn(fee_estimation_result.error_message)
            return fee_estimation_result
        except (requests.exceptions.Timeout, urllib3.exceptions.ReadTimeoutError) as to:
            fee_estimation_result.error_message = f"Timeout while fetching fee estimation from custom provider (timeout {timeout}). Using Bitcoin Core instead."

    fee_estimation_result.result = {
        "fastestFee": int(
            (float(specter.estimatesmartfee(1).get("feerate", 0.00001)) / 1000) * 1e8
        ),
        "halfHourFee": int(
            (float(specter.estimatesmartfee(3).get("feerate", 0.00001)) / 1000) * 1e8
        ),
        "hourFee": int(
            (float(specter.estimatesmartfee(6).get("feerate", 0.00001)) / 1000) * 1e8
        ),
        "minimumFee": int(
            (float(specter.estimatesmartfee(20).get("feerate", 0.00001)) / 1000) * 1e8
        ),
    }
    if "feerate" not in specter.estimatesmartfee(1):
        fee_estimation_result.error_message = "There was an issue while fetching fee estimation with  Bitcoin core. Please use manual fee estimation"
    if not fee_estimation_result.error_message:
        logger.warn(fee_estimation_result.error_message)
    return fee_estimation_result

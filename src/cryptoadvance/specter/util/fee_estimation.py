import logging
from json import JSONEncoder

import requests
import urllib3
from requests.exceptions import ConnectionError

logger = logging.getLogger(__name__)


class FeeEstimationResult:
    """A tiny object to pass the Fee Estimation Results around including a list of errors which might have occurred"""

    def __init__(self, result):
        self.result = result
        self._error_messages = []

    @property
    def error_messages(self):
        return self._error_messages

    @property
    def error_message(self):
        return " AND ".join(self.error_messages)

    @property
    def result(self):
        return self._result

    @result.setter
    def result(self, value):
        self._result = value

    def add_error_message(self, message):
        """Appends an error-message to the list of existing ones"""
        self._error_messages.append(message)


class FeeEstimationResultEncoder(JSONEncoder):
    def default(self, o):
        raw = o.__dict__
        raw["result"] = raw["_result"]
        del raw["_result"]
        raw["error_messages"] = raw["_error_messages"]
        del raw["_error_messages"]
        return raw


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
        fee_estimation.add_error_message(
            f"Failed to Fetch fee estimation. Please use manual fee calculation, check the logs for details. Error: {e}"
        )
        logger.exception(e)
        return fee_estimation


def _get_fees(specter, config):
    fee_estimation_result = FeeEstimationResult(
        {
            "fastestFee": 1,
            "halfHourFee": 1,
            "hourFee": 1,
            "minimumFee": 1,
        }
    )  # Just in case we have errors and no result is set, deliver some defaults which don't break anything
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
        except (
            requests.exceptions.Timeout,
            urllib3.exceptions.ReadTimeoutError,
            ConnectionError,
        ) as to:
            # Timeout is effectively one of the two:
            # ConnectTimeout: The request timed out while trying to connect to the remote server
            # ReadTimeout: The server did not send any data in the allotted amount of time.
            # ReadTimeoutError: Raised when a socket timeout occurs while receiving data from a server

            # Try without Tor if failed, or fall back to Bitcoin Core if only Tor is on
            if to.__class__.__name__ == "ConnectionError":
                issue_text = "Tor not working"
            else:
                issue_text = "Timeout"

            fee_estimation_result.add_error_message(
                f"{issue_text} while fetching fee estimation from mempool.space Tor hidden service (timeout {timeout})."
            )
            if not specter.only_tor:
                try:
                    requests_session = specter.requests_session(force_tor=False)
                    fee_estimation_result.result = requests_session.get(
                        f"{config['EXPLORERS_LIST']['MEMPOOL_SPACE']['url']}api/v1/fees/recommended",
                        timeout=timeout,
                    ).json()
                    fee_estimation_result.add_error_message(
                        f"Using mempool.space without Tor instead."
                    )
                    logger.warn(fee_estimation_result.error_message)
                    return fee_estimation_result
                except (
                    requests.exceptions.Timeout,
                    urllib3.exceptions.ReadTimeoutError,
                ) as to:
                    pass

            fee_estimation_result.add_error_message(f"Using Bitcoin Core instead.")

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
            fee_estimation_result.add_error_message(
                f"Timeout while fetching fee estimation from custom provider (timeout {timeout}). Using Bitcoin Core instead."
            )

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
    fee_estimate = specter.estimatesmartfee(1)
    if "feerate" not in fee_estimate:
        # regtest does not seem to have a reasonable result for estimatesmartfee.
        # The error-message is covering "transactions" and so the cypress-tests are not succeeding
        # Not a perfect fix but better than to fix it everywhere in the test-code:
        if specter.chain != "regtest":
            fee_estimation_result.add_error_message(
                "There was an issue while fetching fee estimation with  Bitcoin core. Please use manual fee estimation"
            )
            for error in fee_estimate.get("errors", []):
                fee_estimation_result.add_error_message(error)
    if fee_estimation_result.error_message:
        logger.warn(fee_estimation_result.error_message)
    return fee_estimation_result

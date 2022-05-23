import logging
import requests
from cryptoadvance.specter.specter_error import SpecterError
from requests.exceptions import ConnectionError, HTTPError
from urllib3.exceptions import NewConnectionError
from json.decoder import JSONDecodeError

logger = logging.getLogger(__name__)


def failsafe_request_get(requests_session, url, parse_json=True):
    """wrapping requests which is only emitting SpecterErrors which are hopefully meaningful to the user"""
    try:
        response: requests.Response = requests_session.get(url)
        if response.status_code != 200:
            response.raise_for_status()
        if not parse_json:
            return response
        json_response = response.json()
        if json_response.get("errors"):
            raise SpecterError(f"JSON error: {json_response}")
        return response.json()
    except JSONDecodeError as e:
        logger.error(f"Got a JSONDecodeError while parsing {response.text} ...")
        raise SpecterError(f"Got a JSONDecodeError while parsing {response.text[:200]}")
    except HTTPError as httpe:
        try:
            json_response = response.json()
        except JSONDecodeError:
            raise SpecterError(f"HttpError {httpe.response.status_code} for {url}")
        logger.debug(f"json-response: {json_response}")
        if json_response.get("errors"):
            raise SpecterError(f"JSON error: {json_response}")
        raise SpecterError(f"HttpError {httpe.response.status_code} for {url}")
    except (ConnectionRefusedError, ConnectionError, NewConnectionError) as e:
        logger.error(
            f"{e} while requesting {url} using proxies http {requests_session.proxies['http']} and https {requests_session.proxies['https']}"
        )
        msg = f"There is a connection issue accessing the url {url}."
        if url and url.endswith(".onion"):
            msg = msg + " Tor might be not working. Please Check your tor setup."
        logger.error(msg)
        raise SpecterError(f"{msg}. Check the logs for more details.")

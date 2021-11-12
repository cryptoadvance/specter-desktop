import json
import logging
import requests
from .manifest import SwanService

SWAN_API_URL = "https://dev-api.swanbitcoin.com/apps/v20210824"


logger = logging.getLogger(__name__)


def get_wallets():
    return _call_api("/wallets", "GET")


def _call_api(path, method="GET", params=None, data=None):
    """call the Swan API"""
    headers = _get_headers(path)
    url = _calc_url(path)
    session = requests.session()
    if data != None:
        data = json.dumps(data)
    logger.debug(f"VTClient Calling {url}")
    logger.debug(f"VTClient method  {method}")
    logger.debug(f"VTClient params  {params}")
    logger.debug(f"VTClient data    {data}")
    logger.debug(f"VTClient headers {headers}")
    response = session.request(
        method,
        url,
        params=params,
        data=data,
        stream=False,
        headers=headers,
    )
    result = response.text
    logger.debug(f"VTClient result {result}")
    try:
        result = json.loads(result)
    except:
        raise Exception(f"Could not json-parse response, got {response.status_code}")
    if result.get("data"):
        return result["data"]
    if result.get("errors"):
        raise Exception(f"got {response.status_code} and error {result['errors']}")
    return result


def _calc_url(path):
    """returns a URL  for the swan-api"""
    return SWAN_API_URL + path


def _get_headers(path):
    """return the VTOKEN, the Content-type and maybe specter-version and -destination"""
    token = SwanService._.get_sec_data().get("access_token")
    headers = {"Authorization": f"Bearer {token}", "Content-type": "application/json"}
    return headers

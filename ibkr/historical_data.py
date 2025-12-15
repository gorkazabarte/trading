from time import sleep
from requests import get, post
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

disable_warnings(InsecureRequestWarning)

BASE_URL = "https://localhost:5001/v1/api/"
SUBSCRIPTION_WAIT_SECONDS = 1


def build_query_params(**params) -> str:
    return "&".join([f"{key}={value}" for key, value in params.items()])


def build_request_url(endpoint: str, query_params: str) -> str:
    return f"{BASE_URL}{endpoint}?{query_params}"


def get_market_data(conid: int, period: str, bar: str):
    endpoint = "hmds/history"

    query_params = build_query_params(
        conid=conid,
        period=period,
        bar=bar,
        outsideRth="true",
        barType="midpoint"
    )

    request_url = build_request_url(endpoint, query_params)
    contract_req = get(request_url, verify=False)

    if contract_req.status_code == 200:
        return contract_req.json()
    else:
        raise Exception(f"Error: {contract_req.status_code}, Response text: {contract_req.text}")


def is_subscription_confirmation(response: list) -> bool:
    if not isinstance(response, list) or len(response) == 0:
        return False

    first_item = response[0]
    return len(first_item.keys()) <= 2 and 'conid' in first_item


def fetch_market_data_with_subscription(request_url: str):
    sleep(SUBSCRIPTION_WAIT_SECONDS)
    contract_req = get(request_url, verify=False)

    if contract_req.status_code == 200:
        return contract_req.json()
    else:
        raise Exception(f"Error on second call: {contract_req.status_code}, Response text: {contract_req.text}")


def try_post_fallback(endpoint: str, conid: int, fields: str):
    json_body = {
        "conids": [conid],
        "fields": fields.split(',')
    }
    contract_req = post(f"{BASE_URL}{endpoint}", json=json_body, verify=False)

    if contract_req.status_code == 200:
        return contract_req.json()
    else:
        raise Exception(f"Error: {contract_req.status_code}, Response text: {contract_req.text}")


def get_market_snapshot(conid: int, fields: str = "31,82,83,84,86,87"):
    endpoint = "iserver/marketdata/snapshot"

    query_params = build_query_params(conids=conid, fields=fields)
    request_url = build_request_url(endpoint, query_params)

    contract_req = get(request_url, verify=False)

    if contract_req.status_code == 200:
        first_response = contract_req.json()

        if is_subscription_confirmation(first_response):
            return fetch_market_data_with_subscription(request_url)
        else:
            return first_response

    elif contract_req.status_code == 400:
        return try_post_fallback(endpoint, conid, fields)
    else:
        raise Exception(f"Error: {contract_req.status_code}, Response text: {contract_req.text}")

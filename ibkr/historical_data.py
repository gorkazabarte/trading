from time import sleep

from requests import get, post
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

disable_warnings(InsecureRequestWarning)

BASE_URL = "https://localhost:5001/v1/api/"
SUBSCRIPTION_WAIT_SECONDS = 2

_subscribed_conids = set()


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


def subscribe_to_market_data(conid: int, fields: str = "31,82,83,84,86,87"):
    """
    Step 1: Subscribe to market data to get real-time prices.
    This is required before polling the snapshot endpoint.
    Only subscribes once per conid.
    """
    global _subscribed_conids

    if conid in _subscribed_conids:
        print(f"DEBUG: conid {conid} already subscribed, skipping")
        return {"status": "already_subscribed"}

    endpoint = "iserver/marketdata/subscribe"

    fields_list = fields.split(',')
    json_body = {
        "conid": conid,
        "fields": fields_list
    }

    print(f"DEBUG: Subscribing to market data for conid {conid} with fields {fields_list}")
    contract_req = post(f"{BASE_URL}{endpoint}", json=json_body, verify=False)

    if contract_req.status_code == 200:
        response = contract_req.json()
        print(f"DEBUG: Subscription response for conid {conid}: {response}")
        _subscribed_conids.add(conid)
        return response
    else:
        print(f"DEBUG: Subscription failed for conid {conid}: {contract_req.status_code} - {contract_req.text}")
        _subscribed_conids.add(conid)
        raise Exception(f"Error subscribing to market data: {contract_req.status_code}, Response text: {contract_req.text}")


def get_market_snapshot(conid: int, fields: str = "31,82,83,84,86,87"):
    """
    Step 2: Poll the subscription stream to get real-time market data.
    First subscribes to market data, then fetches the snapshot.
    """
    endpoint = "iserver/marketdata/snapshot"

    # Step 1: Ensure subscription (only happens once per conid)
    is_new_subscription = conid not in _subscribed_conids

    try:
        result = subscribe_to_market_data(conid, fields)
        if is_new_subscription:
            sleep(SUBSCRIPTION_WAIT_SECONDS)
    except Exception as e:
        pass

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

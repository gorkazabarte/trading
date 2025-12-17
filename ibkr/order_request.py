from typing import Optional, Dict, Any
from requests import Response, get, post

from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

disable_warnings(InsecureRequestWarning)

BASE_URL = "https://localhost:5001/v1/api/"
HTTP_OK = 200

ACCOUNT_ID_KEY = "acctId"
ACCOUNTS_ENDPOINT = "iserver/accounts"
ACCOUNT_SWITCH_ENDPOINT = "iserver/account"
ACCOUNTS_KEY = "accounts"
CONID_KEY = "conid"
ERROR_KEY = "error"
ID_KEY = "id"
ORDER_TYPE_KEY = "orderType"
ORDERS_KEY = "orders"
PRICE_KEY = "price"
QUANTITY_KEY = "quantity"
REPLY_ENDPOINT_PREFIX = "iserver/reply"
RESPONSE_KEY = "response"
SELECTED_ACCOUNT_KEY = "selectedAccount"
SIDE_KEY = "side"
SUCCESS_KEY = "success"
TIF_KEY = "tif"

ACTION_BUY = "BUY"
ACTION_SELL = "SELL"
MAX_CONFIRMATION_ROUNDS = 5
MESSAGE_KEY = "message"
ORDER_ID_KEY = "orderId"
ORDER_TYPE_LIMIT = "LIMIT"
ORDER_TYPE_MARKET = "MARKET"
TIME_IN_FORCE_DAY = "DAY"


def build_url(endpoint: str) -> str:
    return BASE_URL + endpoint


def create_error_response(error_message: str) -> Dict[str, Any]:
    return {SUCCESS_KEY: False, ERROR_KEY: error_message}


def create_success_response(**kwargs) -> Dict[str, Any]:
    result = {SUCCESS_KEY: True}
    result.update(kwargs)
    return result


def extract_account_from_dict(data: Dict) -> Optional[str]:
    if SELECTED_ACCOUNT_KEY in data:
        return data[SELECTED_ACCOUNT_KEY]

    if ACCOUNTS_KEY in data and isinstance(data[ACCOUNTS_KEY], list):
        accounts = data[ACCOUNTS_KEY]
        return accounts[0] if accounts else None

    return None


def extract_account_from_list(data: list) -> Optional[str]:
    return data[0] if data else None


def extract_account_id(data: Any) -> Optional[str]:
    if isinstance(data, dict):
        return extract_account_from_dict(data)
    elif isinstance(data, list):
        return extract_account_from_list(data)
    return None


def get_account_id() -> Optional[str]:
    try:
        response = get(url=build_url(ACCOUNTS_ENDPOINT), verify=False)

        if response.status_code != HTTP_OK:
            return None

        data = response.json()
        return extract_account_id(data)
    except Exception:
        return None


def is_successful_response(response: Response) -> bool:
    return response.status_code == HTTP_OK


def parse_json_safely(response: Response) -> Any:
    try:
        return response.json()
    except Exception:
        return response.text


def switch_account(account_id: str) -> Dict[str, Any]:
    try:
        payload = {ACCOUNT_ID_KEY: account_id}
        response = post(url=build_url(ACCOUNT_SWITCH_ENDPOINT), json=payload, verify=False)

        if is_successful_response(response):
            return create_success_response(response=parse_json_safely(response))

        return create_error_response(f"Status {response.status_code}: {response.text}")
    except Exception as e:
        return create_error_response(str(e))


def build_order_endpoint(account_id: str) -> str:
    return f"iserver/account/{account_id}/orders"


def build_order_payload(conid: int, order_type: str, action: str, quantity: int, price: Optional[float]) -> Dict[str, Any]:
    order_data = {
        CONID_KEY: conid,
        ORDER_TYPE_KEY: order_type,
        SIDE_KEY: action,
        TIF_KEY: TIME_IN_FORCE_DAY,
        QUANTITY_KEY: quantity
    }

    if order_type == ORDER_TYPE_LIMIT and price is not None:
        order_data[PRICE_KEY] = float(price)

    return {ORDERS_KEY: [order_data]}


def ensure_account_id(account_id: Optional[str]) -> Optional[str]:
    return account_id if account_id else get_account_id()


def handle_http_error(status_code: int, response_text: str) -> Dict[str, Any]:
    return {
        SUCCESS_KEY: False,
        ERROR_KEY: f"HTTP {status_code}: {response_text}",
        RESPONSE_KEY: response_text
    }


def handle_json_parse_error(error: Exception, response_text: str, status_code: int) -> Dict[str, Any]:
    return {
        SUCCESS_KEY: False,
        ERROR_KEY: f"Failed to parse response as JSON: {str(error)}",
        RESPONSE_KEY: response_text,
        "status_code": status_code
    }


def has_order_id(response_data: Any) -> bool:
    return (isinstance(response_data, list) and
            len(response_data) > 0 and
            ID_KEY in response_data[0])


def is_confirmation_required(response_data: Any) -> bool:
    if not isinstance(response_data, list) or len(response_data) == 0:
        return False

    first_item = response_data[0]
    return ID_KEY in first_item and MESSAGE_KEY in first_item


def is_order_placed(response_data: Any) -> bool:
    if not isinstance(response_data, list) or len(response_data) == 0:
        return False

    first_item = response_data[0]
    return ORDER_ID_KEY in first_item


def confirm_order(reply_id: str) -> Any:
    endpoint = f"{REPLY_ENDPOINT_PREFIX}/{reply_id}"
    confirmation_body = {"confirmed": True}  # Python True converts to JSON true
    response = post(url=build_url(endpoint), json=confirmation_body, verify=False)

    if not is_successful_response(response):
        return []

    try:
        result = response.json()
        return result if result else []
    except Exception:
        return []


def order_request(account_id: str, action: str, conid: int, quantity: int, order_type: str, price: Optional[float]) -> Dict[str, Any]:
    try:
        endpoint = build_order_endpoint(account_id)
        payload = build_order_payload(conid, order_type, action, quantity, price)

        response = post(url=build_url(endpoint), json=payload, verify=False)

        if not is_successful_response(response):
            return handle_http_error(response.status_code, response.text)

        try:
            order_json = response.json()
        except Exception as json_error:
            return handle_json_parse_error(json_error, response.text, response.status_code)

        confirmation_round = 0
        responses_history = [order_json]

        while confirmation_round < MAX_CONFIRMATION_ROUNDS:
            if is_order_placed(order_json):
                return create_success_response(
                    initial_response=order_json,
                    confirmation_response=order_json,
                    confirmation_rounds=confirmation_round,
                    responses_history=responses_history
                )

            if is_confirmation_required(order_json):
                reply_id = order_json[0][ID_KEY]
                order_json = confirm_order(reply_id)
                confirmation_round += 1

                if order_json and len(order_json) > 0:
                    responses_history.append(order_json)
                else:
                    return create_error_response(
                        f"Empty response after confirmation round {confirmation_round}. History: {responses_history}"
                    )
            else:
                break

        if is_order_placed(order_json):
            return create_success_response(
                initial_response=order_json,
                confirmation_response=order_json,
                confirmation_rounds=confirmation_round,
                responses_history=responses_history
            )

        return create_error_response(
            f"Order not placed after {confirmation_round} confirmation rounds. History: {responses_history}"
        )

    except Exception as e:
        return create_error_response(f"Exception: {str(e)}")


def prepare_order(conid: int, quantity: int, account_id: Optional[str], action: str, order_type: str, price: Optional[float]) -> Dict[str, Any]:
    account = ensure_account_id(account_id)

    if not account:
        return create_error_response("Unable to fetch account ID")

    switch_result = switch_account(account)

    if not switch_result.get(SUCCESS_KEY):
        error_msg = switch_result.get(ERROR_KEY, "Account switch failed")
        return create_error_response(f"Failed to switch to account {account}: {error_msg}")

    return order_request(account, action, conid, quantity, order_type, price)


def place_buy_order(conid: int, quantity: int, price: float, account_id: Optional[str] = None) -> Dict[str, Any]:
    return prepare_order(conid, quantity, account_id, ACTION_BUY, ORDER_TYPE_LIMIT, price)


def place_market_buy_order(conid: int, quantity: int, account_id: Optional[str] = None) -> Dict[str, Any]:
    return prepare_order(conid, quantity, account_id, ACTION_BUY, ORDER_TYPE_MARKET, None)


def place_market_sell_order(conid: int, quantity: int, account_id: Optional[str] = None) -> Dict[str, Any]:
    return prepare_order(conid, quantity, account_id, ACTION_SELL, ORDER_TYPE_MARKET, None)


def place_sell_order(conid: int, quantity: int, price: float, account_id: Optional[str] = None) -> Dict[str, Any]:
    return prepare_order(conid, quantity, account_id, ACTION_SELL, ORDER_TYPE_LIMIT, price)

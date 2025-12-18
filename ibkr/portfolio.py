from typing import Dict, Any
from requests import Response, get

from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

disable_warnings(InsecureRequestWarning)

BASE_URL = "https://localhost:5001/v1/api/"
HTTP_OK = 200
PAGE_ID_ALL = 0

ACCOUNT_ID_KEY = "acctId"
ACCOUNTS_ENDPOINT = "portfolio/accounts"
ASSET_CLASS_KEY = "assetClass"
AVERAGE_COST_KEY = "avgCost"
AVERAGE_PRICE_KEY = "avgPrice"
CONID_KEY = "conid"
CONTRACT_DESC_KEY = "contractDesc"
CURRENCY_KEY = "currency"
ERROR_KEY = "error"
MARKET_PRICE_KEY = "mktPrice"
MARKET_VALUE_KEY = "mktValue"
MESSAGE_KEY = "message"
POSITIONS_ENDPOINT_FORMAT = "portfolio/{}/positions/{}"
POSITIONS_KEY = "positions"
POSITION_KEY = "position"
REALIZED_PNL_KEY = "realizedPnl"
SUCCESS_KEY = "success"
TICKER_KEY = "ticker"
UNREALIZED_PNL_KEY = "unrealizedPnl"


def build_error_response(error_message: str) -> Dict[str, Any]:
    return {
        SUCCESS_KEY: False,
        ERROR_KEY: error_message,
        POSITIONS_KEY: []
    }


def build_positions_url(account_id: str) -> str:
    endpoint = POSITIONS_ENDPOINT_FORMAT.format(account_id, PAGE_ID_ALL)
    return BASE_URL + endpoint


def build_success_response(positions: list, **kwargs) -> Dict[str, Any]:
    result = {
        SUCCESS_KEY: True,
        POSITIONS_KEY: positions
    }
    result.update(kwargs)
    return result


def build_url(endpoint: str) -> str:
    return BASE_URL + endpoint


def extract_account_id(accounts_data: Any) -> str:
    if isinstance(accounts_data, list):
        return str(accounts_data[0].get('id'))
    elif isinstance(accounts_data, dict):
        return str(accounts_data.get(ACCOUNT_ID_KEY, accounts_data.get('accountId', '')))
    return str(accounts_data)


def fetch_accounts() -> Response:
    return get(url=build_url(ACCOUNTS_ENDPOINT), verify=False)


def fetch_positions_for_account(account_id: str) -> Response:
    return get(url=build_positions_url(account_id), verify=False)


def format_pnl(unrealized_pnl: float) -> str:
    if unrealized_pnl >= 0:
        return f"+${unrealized_pnl:.2f}"
    return f"-${abs(unrealized_pnl):.2f}"


def format_position_summary(position: Dict) -> str:
    ticker = position.get(TICKER_KEY, "N/A")
    quantity = position.get(POSITION_KEY, 0)
    avg_price = position.get(AVERAGE_PRICE_KEY, 0)
    mkt_price = position.get(MARKET_PRICE_KEY, 0)
    unrealized = position.get(UNREALIZED_PNL_KEY, 0)

    pnl_str = format_pnl(unrealized)

    return f"{ticker}: {quantity} shares @ ${avg_price:.2f} (Now: ${mkt_price:.2f}, P/L: {pnl_str})"


def get_account_positions(account_id: str) -> Dict[str, Any]:
    try:
        response = fetch_positions_for_account(account_id)

        if is_successful_response(response):
            positions = parse_positions_response(response)
            return build_success_response(positions)

        return handle_failed_response(response)
    except Exception as e:
        return build_error_response(str(e))


def get_all_positions() -> Dict[str, Any]:
    try:
        accounts_response = fetch_accounts()

        if not is_successful_response(accounts_response):
            error_msg = f"Failed to fetch accounts: HTTP {accounts_response.status_code}"
            return build_error_response(error_msg)

        accounts = accounts_response.json()

        if not has_accounts(accounts):
            return build_success_response([], message="No accounts found")

        account_id = extract_account_id(accounts)
        return get_account_positions(account_id)

    except Exception as e:
        return build_error_response(str(e))


def handle_failed_response(response: Response) -> Dict[str, Any]:
    error_msg = f"HTTP {response.status_code}: {response.text}"
    return build_error_response(error_msg)


def has_accounts(accounts: Any) -> bool:
    return accounts is not None and (
        (isinstance(accounts, list) and len(accounts) > 0) or
        (not isinstance(accounts, list))
    )


def is_successful_response(response: Response) -> bool:
    return response.status_code == HTTP_OK


def parse_position(position: Dict) -> Dict[str, Any]:
    return {
        "account_id": position.get(ACCOUNT_ID_KEY),
        "asset_class": position.get(ASSET_CLASS_KEY),
        "average_cost": position.get(AVERAGE_COST_KEY),
        "average_price": position.get(AVERAGE_PRICE_KEY),
        "conid": position.get(CONID_KEY),
        "contract_desc": position.get(CONTRACT_DESC_KEY),
        "currency": position.get(CURRENCY_KEY),
        "market_price": position.get(MARKET_PRICE_KEY),
        "market_value": position.get(MARKET_VALUE_KEY),
        "position": position.get(POSITION_KEY),
        "realized_pnl": position.get(REALIZED_PNL_KEY),
        "ticker": position.get(TICKER_KEY),
        "unrealized_pnl": position.get(UNREALIZED_PNL_KEY)
    }


def parse_positions_response(response: Response) -> list:
    positions = response.json()
    return positions if positions else []


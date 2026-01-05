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


def fetch_and_sync_positions(logger, s3_client):
    """Fetch positions from IBKR and sync to local and S3 storage."""
    from services.ibkr.ib_gateway_client import get_ib_client
    from utils.file_operations import write_json_to_file
    from utils.time_utils import get_current_date

    logger.info("Fetching current positions from IBKR...")
    ib_client = get_ib_client()

    if not ib_client.connected:
        logger.warning("IB Gateway not connected - cannot fetch positions")
        return

    positions = ib_client.get_positions()

    if not positions or len(positions) == 0:
        logger.info("No open positions found in IBKR account")
        year, month, day = get_current_date()
        local_path = f'./files/open_positions.json'
        write_json_to_file(local_path, {})
        logger.info("Created empty open_positions.json at ./files/open_positions.json")

        try:
            s3_client.upload_file(local_path, 'dev-trading-data-storage', 'open_positions.json')
            logger.info("Uploaded empty open_positions.json to S3")
        except Exception as e:
            logger.error(f"Failed to upload empty open_positions.json to S3: {e}")
        return

    save_positions_to_files(positions, s3_client, logger)


def save_positions_to_files(positions_dict: Dict, year: int, month: int, day: int, s3_client):
    """Save positions to local file and S3."""
    from utils.file_operations import write_json_to_file
    from datetime import datetime, timezone

    for ticker, position_data in positions_dict.items():
        position_data['timestamp'] = datetime.now(timezone.utc).isoformat()
        position_data['date'] = f"{year}-{month:02d}-{day:02d}"

    local_path = './files/open_positions.json'
    write_json_to_file(local_path, positions_dict)

    try:
        s3_client.upload_file(local_path, 'dev-trading-data-storage', 'open_positions.json')
    except Exception:
        pass


def save_closed_positions_to_s3(year: int, month: int, day: int, s3_client, logger):
    """Save closed positions for the day to S3."""
    from core.state import get_closed_positions
    from utils.file_operations import write_json_to_file

    closed_positions = get_closed_positions()

    if not closed_positions:
        return

    total_profit = sum(p.get('profit', 0) for p in closed_positions)
    logger.info(f"Saved {len(closed_positions)} closed position(s) to: ./files/{year}/{month:02d}/{day:02d}/closed_positions.json")
    logger.info(f"Total P/L for the day: ${total_profit:.2f}")

    local_path = f'./files/{year}/{month:02d}/{day:02d}/closed_positions.json'
    write_json_to_file(local_path, closed_positions)

    s3_key = f'{year}/{month:02d}/{day:02d}/closed_positions.json'

    try:
        s3_client.upload_file(local_path, 'dev-trading-data-storage', s3_key)
        logger.info(f"Closed positions uploaded to S3: s3://dev-trading-data-storage/{s3_key}")
    except Exception as e:
        logger.error(f"Failed to upload closed positions to S3: {e}")




from typing import Any, Dict

from requests import Response, get
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

disable_warnings(InsecureRequestWarning)

ACCOUNT_ID_KEY = "acctId"
ACCOUNTS_ENDPOINT = "portfolio/accounts"
ASSET_CLASS_KEY = "assetClass"
AVERAGE_COST_KEY = "avgCost"
AVERAGE_PRICE_KEY = "avgPrice"
BASE_URL = "https://localhost:5001/v1/api/"
CONID_KEY = "conid"
CONTRACT_DESC_KEY = "contractDesc"
CURRENCY_KEY = "currency"
ERROR_KEY = "error"
HTTP_OK = 200
MARKET_PRICE_KEY = "mktPrice"
MARKET_VALUE_KEY = "mktValue"
MESSAGE_KEY = "message"
PAGE_ID_ALL = 0
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


def clear_open_positions(s3_client, logger):
    from utils.file_operations import write_json_to_file

    local_path = get_open_positions_file_path()
    write_json_to_file(local_path, {})
    logger.info("Cleared open_positions.json")

    try:
        s3_client.upload_file(local_path, 'dev-trading-data-storage', 'open_positions.json')
        logger.info("Uploaded cleared open_positions.json to S3")
    except Exception as e:
        logger.error(f"Failed to upload cleared open_positions.json to S3: {e}")


def convert_positions_list_to_dict(positions_list: list) -> Dict:
    positions_dict = {}
    for position in positions_list:
        ticker = position.get('ticker')
        if ticker:
            positions_dict[ticker] = position
    return positions_dict


def extract_account_id(accounts_data: Any) -> str:
    if isinstance(accounts_data, list):
        return str(accounts_data[0].get('id'))
    elif isinstance(accounts_data, dict):
        return str(accounts_data.get(ACCOUNT_ID_KEY, accounts_data.get('accountId', '')))
    return str(accounts_data)


def extract_filled_tickers(ibkr_positions: list) -> set:
    filled_tickers = set()
    if not ibkr_positions:
        return filled_tickers

    for pos in ibkr_positions:
        ticker = pos.get('ticker')
        position = pos.get('position', 0)
        if ticker and position > 0:
            filled_tickers.add(ticker)

    return filled_tickers


def fetch_accounts() -> Response:
    return get(url=build_url(ACCOUNTS_ENDPOINT), verify=False)


def fetch_and_sync_positions(logger, s3_client):
    from services.ibkr.ib_gateway_client import get_ib_client
    from utils.file_operations import write_json_to_file

    logger.info("Fetching current positions from IBKR...")
    ib_client = get_ib_client()

    if not ib_client.connected:
        logger.warning("IB Gateway not connected - cannot fetch positions")
        return

    positions = ib_client.get_positions()

    if not positions or len(positions) == 0:
        logger.info("No open positions found in IBKR account")

        if open_positions_file_exists():
            existing_positions = load_open_positions()
            if existing_positions:
                logger.info(f"Preserving {len(existing_positions)} pending order(s)")
                return

        local_path = './files/open_positions.json'
        write_json_to_file(local_path, {})
        logger.info("Created empty open_positions.json at ./files/open_positions.json")

        try:
            s3_client.upload_file(local_path, 'dev-trading-data-storage', 'open_positions.json')
            logger.info("Uploaded empty open_positions.json to S3")
        except Exception as e:
            logger.error(f"Failed to upload empty open_positions.json to S3: {e}")
        return

    existing_positions = load_open_positions() if open_positions_file_exists() else {}
    merged_positions = merge_positions_with_order_data(positions, existing_positions)
    save_and_upload_positions(merged_positions, s3_client, logger)


def fetch_positions_for_account(account_id: str) -> Response:
    return get(url=build_positions_url(account_id), verify=False)


def format_order_status_display(ticker: str, position_data: Dict, market_data: Dict) -> str:
    last_price = market_data.get('last_price', 'N/A')
    bid_price = market_data.get('bid_price', 'N/A')
    ask_price = market_data.get('ask_price', 'N/A')

    filled = position_data.get('filled', False)
    order_status = position_data.get('order_status', 'UNKNOWN')
    order_type = position_data.get('order_type', 'N/A')
    order_price = position_data.get('order_price', 'N/A')
    take_profit_price = position_data.get('take_profit_price', 'N/A')
    stop_loss_price = position_data.get('stop_loss_price', 'N/A')

    status_display = "FILLED" if filled else order_status
    order_type_display = f"BUY {order_type}" if order_type != 'N/A' else 'N/A'

    last_str = f"${last_price:.2f}" if isinstance(last_price, (int, float)) else str(last_price)
    bid_str = f"${bid_price:.2f}" if isinstance(bid_price, (int, float)) else str(bid_price)
    ask_str = f"${ask_price:.2f}" if isinstance(ask_price, (int, float)) else str(ask_price)
    order_price_str = f"${order_price:.2f}" if isinstance(order_price, (int, float)) else str(order_price)
    take_profit_str = f"${take_profit_price:.2f}" if isinstance(take_profit_price, (int, float)) else str(take_profit_price)
    stop_loss_str = f"${stop_loss_price:.2f}" if isinstance(stop_loss_price, (int, float)) else str(stop_loss_price)

    return (f"{ticker} | Last: {last_str} | Bid: {bid_str} | Ask: {ask_str} | "
            f"Status: {status_display} | {order_type_display} @ {order_price_str} | "
            f"TP: {take_profit_str} | SL: {stop_loss_str}")



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


def get_open_positions_file_path() -> str:
    return './files/open_positions.json'


def handle_failed_response(response: Response) -> Dict[str, Any]:
    error_msg = f"HTTP {response.status_code}: {response.text}"
    return build_error_response(error_msg)


def has_accounts(accounts: Any) -> bool:
    return accounts is not None and (
        (isinstance(accounts, list) and len(accounts) > 0) or
        (not isinstance(accounts, list))
    )


def is_ib_gateway_connected(ib_client, logger) -> bool:
    if not ib_client.connected:
        logger.warning("IB Gateway not connected - cannot update order fill status")
        return False
    return True


def is_order_pending(position_data: Dict) -> bool:
    return not position_data.get('filled', False)


def is_successful_response(response: Response) -> bool:
    return response.status_code == HTTP_OK


def log_order_statuses(logger, market_data_by_ticker: Dict) -> None:
    if not open_positions_file_exists():
        return

    try:
        open_positions = load_open_positions()

        if not open_positions:
            logger.info("No open orders to display")
            return

        logger.info("=" * 80)
        logger.info("ORDER STATUS SUMMARY")
        logger.info("=" * 80)

        for ticker, position_data in sorted(open_positions.items()):
            market_data = market_data_by_ticker.get(ticker, {})
            status_line = format_order_status_display(ticker, position_data, market_data)
            logger.info(status_line)

        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Error logging order statuses: {e}")


def load_open_positions() -> Dict:
    from utils.file_operations import read_json_from_file
    return read_json_from_file(get_open_positions_file_path())


def mark_order_as_filled(position_data: Dict) -> None:
    position_data['filled'] = True
    position_data['order_status'] = 'FILLED'


def merge_positions_with_order_data(ibkr_positions_list: list, existing_positions: Dict) -> Dict:
    from datetime import datetime, timezone
    from utils.time_utils import get_current_date

    year, month, day = get_current_date()
    merged = {}

    for position in ibkr_positions_list:
        ticker = position.get('ticker')
        if not ticker:
            continue

        existing_data = existing_positions.get(ticker, {})

        merged[ticker] = {
            'ticker': ticker,
            'conid': position.get('conid'),
            'position': position.get('position'),
            'average_price': position.get('average_price'),
            'market_price': position.get('market_price'),
            'market_value': position.get('market_value'),
            'unrealized_pnl': position.get('unrealized_pnl'),
            'currency': position.get('currency'),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'date': f"{year}-{month:02d}-{day:02d}",
            'filled': True,
            'order_status': 'FILLED',
            'order_type': existing_data.get('order_type', 'N/A'),
            'order_price': existing_data.get('order_price', 'N/A'),
            'take_profit_price': existing_data.get('take_profit_price', 'N/A'),
            'stop_loss_price': existing_data.get('stop_loss_price', 'N/A'),
        }

    for ticker, existing_data in existing_positions.items():
        if ticker not in merged and not existing_data.get('filled', False):
            merged[ticker] = existing_data

    return merged


def open_positions_file_exists() -> bool:
    from os import path
    return path.exists(get_open_positions_file_path())


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


def save_and_upload_positions(open_positions: Dict, s3_client, logger) -> None:
    save_open_positions_locally(open_positions)
    upload_open_positions_to_s3(s3_client, logger)


def save_closed_positions_to_s3(year: int, month: int, day: int, s3_client, logger):
    from core.state import get_closed_positions
    from utils.file_operations import write_json_to_file

    closed_positions = get_closed_positions()

    if not closed_positions:
        logger.info("No closed positions to save for today")
        return

    total_profit = sum(p.get('profit', 0) for p in closed_positions)
    winning_trades = sum(1 for p in closed_positions if p.get('profit', 0) > 0)
    losing_trades = sum(1 for p in closed_positions if p.get('profit', 0) < 0)

    logger.info(f"Day Summary - Closed {len(closed_positions)} position(s)")
    logger.info(f"Winning trades: {winning_trades} | Losing trades: {losing_trades}")
    logger.info(f"Total P/L for the day: ${total_profit:.2f}")

    local_path = f'./files/{year}/{month:02d}/{day:02d}/closed_positions.json'
    write_json_to_file(local_path, closed_positions)
    logger.info(f"Saved closed positions to: {local_path}")

    s3_key = f'{year}/{month:02d}/{day:02d}/closed_positions.json'

    try:
        s3_client.upload_file(local_path, 'dev-trading-data-storage', s3_key)
        logger.info(f"Closed positions uploaded to S3: s3://dev-trading-data-storage/{s3_key}")
    except Exception as e:
        logger.error(f"Failed to upload closed positions to S3: {e}")


def save_open_positions_locally(open_positions: Dict) -> None:
    from utils.file_operations import write_json_to_file
    write_json_to_file(get_open_positions_file_path(), open_positions)


def save_positions_to_files(positions_dict: Dict, year: int, month: int, day: int, s3_client):
    from datetime import datetime, timezone
    from utils.file_operations import write_json_to_file

    for ticker, position_data in positions_dict.items():
        position_data['timestamp'] = datetime.now(timezone.utc).isoformat()
        position_data['date'] = f"{year}-{month:02d}-{day:02d}"

    local_path = './files/open_positions.json'
    write_json_to_file(local_path, positions_dict)

    try:
        s3_client.upload_file(local_path, 'dev-trading-data-storage', 'open_positions.json')
    except Exception:
        pass


def update_all_positions_status(open_positions: Dict, filled_tickers: set, logger) -> bool:
    updated = False
    for ticker, position_data in open_positions.items():
        if update_position_if_filled(ticker, position_data, filled_tickers, logger):
            updated = True
    return updated


def update_market_prices(logger, s3_client, market_data_by_ticker: Dict):
    if not open_positions_file_exists():
        return

    try:
        open_positions = load_open_positions()

        if not open_positions:
            return

        updated = False
        for ticker, position_data in open_positions.items():
            market_data = market_data_by_ticker.get(ticker, {})
            last_price = market_data.get('last_price')

            if last_price and position_data.get('market_price') != last_price:
                position_data['market_price'] = last_price
                position_data['market_value'] = last_price * position_data.get('position', 0)
                updated = True

        if updated:
            save_and_upload_positions(open_positions, s3_client, logger)

    except Exception as e:
        logger.error(f"Error updating market prices: {e}")


def update_order_fill_status(logger, s3_client):
    from services.ibkr.ib_gateway_client import get_ib_client

    if not open_positions_file_exists():
        return

    try:
        open_positions = load_open_positions()

        if not open_positions:
            return

        ib_client = get_ib_client()
        if not is_ib_gateway_connected(ib_client, logger):
            return

        ibkr_positions = ib_client.get_positions()
        filled_tickers = extract_filled_tickers(ibkr_positions)

        if filled_tickers:
            logger.info(f"Found {len(filled_tickers)} filled position(s) in IBKR: {', '.join(sorted(filled_tickers))}")

        pending_tickers = [t for t, p in open_positions.items() if is_order_pending(p)]
        if pending_tickers:
            logger.info(f"Pending orders in open_positions.json: {', '.join(sorted(pending_tickers))}")

        updated = update_all_positions_status(open_positions, filled_tickers, logger)

        if updated:
            save_and_upload_positions(open_positions, s3_client, logger)
        elif pending_tickers:
            logger.info("No order status updates detected")

    except Exception as e:
        logger.error(f"Error updating order fill status: {e}")


def update_position_if_filled(ticker: str, position_data: Dict, filled_tickers: set, logger) -> bool:
    if is_order_pending(position_data) and ticker in filled_tickers:
        mark_order_as_filled(position_data)
        logger.info(f"{ticker} - Order FILLED, updating open_positions.json")
        return True
    return False


def upload_open_positions_to_s3(s3_client, logger) -> None:
    try:
        s3_client.upload_file(
            get_open_positions_file_path(),
            'dev-trading-data-storage',
            'open_positions.json'
        )
        logger.info("Updated open_positions.json uploaded to S3")
    except Exception as e:
        logger.error(f"Failed to upload updated open_positions.json to S3: {e}")



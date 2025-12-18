from datetime import datetime, timezone, timedelta, time
from json import dumps, loads
from logging import INFO, Logger
from os import makedirs, path
from typing import Dict, List, Optional

from boto3 import client

from ibkr.contract_details import contract_search
from ibkr.historical_data import get_market_snapshot
from ibkr.market_data_parser import format_market_data_log, parse_market_data
from ibkr.order_request import place_market_buy_order, place_market_sell_order
from ibkr.portfolio import format_position_summary, get_all_positions, parse_position
from logs.setup import setup_logging

MARKET_CLOSE_TIME = time(16, 0)
MINUTES_BEFORE_CLOSE_TO_SELL = 10
S3_BUCKET = 'dev-trading-data-storage'
SETTINGS_FILE_PATH = 'files/settings.json'
UPDATE_INTERVAL = 0

bought_shares_today: Dict[str, Dict[str, any]] = {}


def calculate_budget_per_trade() -> float:
    """
    Calculate the budget per trade based on settings.
    Formula: nextInvestment / opsPerDay
    Returns 0 if settings cannot be loaded or calculation fails.
    """
    try:
        settings = load_settings()
        next_investment = settings.get('nextInvestment', 0)
        ops_per_day = settings.get('opsPerDay', 1)

        if next_investment > 0 and ops_per_day > 0:
            return next_investment / ops_per_day

        return 0
    except Exception:
        return 0


def calculate_quantity_from_budget(current_price: float) -> int:
    """
    Calculate the number of shares to buy based on the budget per trade.
    Buys as many shares as possible without exceeding the budget.
    Returns at least 1 share if budget allows, otherwise 0.
    """
    budget = calculate_budget_per_trade()

    if budget <= 0 or current_price <= 0:
        return 1

    quantity = int(budget / current_price)

    return max(1, quantity)


def load_settings() -> Dict:
    """Load settings from local settings.json file."""
    try:
        with open(SETTINGS_FILE_PATH, 'r') as f:
            return loads(f.read())
    except Exception:
        return {}


def create_company_data(ticker: str, parsed_data: Dict, closing_price: Optional[str], year: int, month: int, day: int) -> Dict:
    now = datetime.now(timezone.utc)

    price_change_from_close_pct = calculate_price_change_from_close(parsed_data.get('last_price'), closing_price)
    price_difference_from_close = calculate_price_difference_from_close(parsed_data.get('last_price'), closing_price)

    return {
        'ticker': ticker,
        'timestamp': now.isoformat(),
        'date': f"{year}-{month:02d}-{day:02d}",
        'conid': parsed_data.get('conid'),
        'last_price': parsed_data.get('last_price'),
        'closing_price': closing_price,
        'price_difference_from_close': price_difference_from_close,
        'price_change_from_close_pct': price_change_from_close_pct,
        'bid_price': parsed_data.get('bid_price'),
        'ask_price': parsed_data.get('ask_price'),
        'volume': parsed_data.get('volume'),
        'volume_raw': parsed_data.get('volume_raw'),
        'spread': parsed_data.get('spread'),
        'spread_percent': parsed_data.get('spread_percent'),
        'is_market_closed': parsed_data.get('is_market_closed'),
        'price_type': parsed_data.get('price_type'),
        'exchange_code': parsed_data.get('exchange_code')
    }


def create_directories(year: int, month: int, day: int) -> str:
    market_data_dir = f'./files/{year}/{month}/{day}'
    makedirs(market_data_dir, exist_ok=True)
    makedirs('./files', exist_ok=True)
    return market_data_dir


def calculate_minutes_until_close(current_time: time) -> int:
    close_datetime = datetime.combine(datetime.today(), MARKET_CLOSE_TIME)
    current_datetime = datetime.combine(datetime.today(), current_time)
    time_diff = close_datetime - current_datetime
    return int(time_diff.total_seconds() / 60)


def calculate_price_change_from_close(last_price: Optional[str], closing_price: Optional[str]) -> Optional[float]:
    if not last_price or not closing_price:
        return None

    try:
        last = float(last_price)
        close = float(closing_price)
        return round(((last - close) / close) * 100, 2)
    except (ValueError, TypeError):
        return None


def calculate_price_difference_from_close(last_price: Optional[str], closing_price: Optional[str]) -> Optional[float]:
    if not last_price or not closing_price:
        return None

    try:
        last = float(last_price)
        close = float(closing_price)
        return round(last - close, 2)
    except (ValueError, TypeError):
        return None


def calculate_price_change_percentage(current_price: float, closing_price: float) -> float:
    return ((current_price - closing_price) / closing_price) * 100


def calculate_buy_range_prices(closing_price: float) -> tuple[float, float]:
    lower_threshold = closing_price * 1.008
    upper_threshold = closing_price * 1.0095
    return lower_threshold, upper_threshold


def format_buy_range(closing_price: float) -> str:
    lower, upper = calculate_buy_range_prices(closing_price)
    return f"[Buy Range: ${lower:.2f} - ${upper:.2f}]"


def determine_closing_price(parsed_data: Dict, existing_closing_price: Optional[str], logger: Logger, ticker: str) -> Optional[str]:
    if should_preserve_existing_closing_price(existing_closing_price):
        logger.info(f"{ticker} - Preserving existing closing price: ${existing_closing_price}")
        return existing_closing_price

    if is_official_closing_price(parsed_data):
        closing_price = parsed_data.get('last_price')
        logger.info(f"{ticker} - Setting closing price: ${closing_price}")
        return closing_price

    if has_previous_close(parsed_data):
        closing_price = parsed_data.get('previous_close')
        logger.info(f"{ticker} - Setting closing price from previous_close: ${closing_price}")
        return closing_price

    return None


def download_companies_list(s3_client, bucket: str, year: int, month: int, day: int, logger: Logger) -> Optional[List[str]]:
    try:
        file_path = f'./files/{year}/{month}/{day}/selected_companies.txt'
        s3_key = f'{year}/{month}/{day}/selected_companies.txt'
        s3_client.download_file(bucket, s3_key, file_path)
        with open(file_path, 'r') as f:
            return f.read().splitlines()
    except Exception as e:
        logger.error(f"Companies were not selected for {year}/{month}/{day}. Error: {str(e)}")
        logger.error(f"Expected S3 location: s3://{bucket}/{year}/{month}/{day}/selected_companies.txt")
        return None


def download_settings_file(s3_client, bucket: str, logger: Logger) -> Optional[Dict]:
    try:
        s3_client.download_file(bucket, 'settings.json', './files/settings.json')
        with open('./files/settings.json', 'r') as f:
            return loads(f.read())
    except Exception as e:
        logger.error(f"Failed to download settings.json: {str(e)}")
        logger.error(f"Expected S3 location: s3://{bucket}/settings.json")
        return None


def fetch_and_parse_market_data(ticker: str, logger: Logger) -> Optional[Dict]:
    try:
        conid = contract_search(ticker)
        logger.info(f"Contract ID for {ticker}: {conid}")

        snapshot = get_market_snapshot(int(conid))

        if not is_valid_snapshot(snapshot):
            logger.warning(f"{ticker} - Empty or invalid snapshot response")
            return None

        market_data = snapshot[0]
        parsed_data = parse_market_data(market_data)
        logger.info(format_market_data_log(ticker, parsed_data))

        return parsed_data

    except Exception as e:
        logger.error(f"{ticker} - Error fetching market data: {e}")
        return None


def get_current_eastern_time() -> time:
    eastern_offset = timedelta(hours=-5)
    eastern_time = datetime.now(timezone.utc) + eastern_offset
    return eastern_time.time()


def get_current_date() -> tuple[int, int, int]:
    now = datetime.now(timezone.utc)
    return now.year, now.month, now.day


def get_existing_closing_price(file_path: str, logger: Logger) -> Optional[str]:
    if not path.exists(file_path):
        return None

    try:
        with open(file_path, 'r') as f:
            existing_data = loads(f.read())
            return existing_data.get('closing_price')
    except Exception as e:
        logger.warning(f"Could not read existing file {file_path}: {e}")
        return None


def handle_buy_action(ticker: str, conid: int, current_price: float, logger: Logger) -> None:
    if ticker in bought_shares_today:
        return

    quantity = calculate_quantity_from_budget(current_price)
    estimated_cost = quantity * current_price

    order_result = place_market_buy_order(
        conid=conid,
        quantity=quantity
    )

    if order_result.get("success"):
        bought_shares_today[ticker] = {
            "buy_price": current_price,
            "conid": conid,
            "quantity": quantity
        }
        logger.info(f"BUY SUCCESS - {ticker}: {quantity} share(s) at MARKET (Est: ${estimated_cost:.2f})")
    else:
        error_msg = order_result.get('error', 'Order request failed with no error message')
        logger.error(f"BUY FAILED - {ticker}: {error_msg}")


def handle_end_of_day_sales(logger: Logger) -> None:
    if not is_close_to_market_close():
        return

    if len(bought_shares_today) == 0:
        return

    logger.info(f"MARKET CLOSING SOON - {len(bought_shares_today)} position(s) to close")

    for ticker in list(bought_shares_today):
        sell_at_market_price(ticker, logger)


def has_previous_close(parsed_data: Dict) -> bool:
    return parsed_data.get('previous_close') is not None


def has_required_dependencies(settings: Optional[Dict], companies: Optional[List[str]]) -> bool:
    return settings is not None and companies is not None


def is_official_closing_price(parsed_data: Dict) -> bool:
    return parsed_data.get('price_type') == 'Closing Price'


def is_valid_snapshot(snapshot: Optional[List]) -> bool:
    return snapshot is not None and len(snapshot) > 0


def log_next_update_time(update_interval: int, logger: Logger) -> None:
    next_update = datetime.now(timezone.utc) + timedelta(seconds=update_interval)
    logger.info(f"Next update at: {next_update.strftime('%Y-%m-%d %H:%M:%S UTC')}")


def evaluate_and_log_trading_opportunity(ticker: str, parsed_data: Dict, closing_price: Optional[str], logger: Logger) -> None:
    current_price = float(parsed_data.get('last_price'))
    close_price_value = float(closing_price)
    conid = int(parsed_data.get('conid'))
    handle_buy_action(ticker, conid, current_price, logger)

    if not should_evaluate_trading_opportunity(parsed_data, closing_price):
        return

    try:
        current_price = float(parsed_data.get('last_price'))
        close_price_value = float(closing_price)
        conid = int(parsed_data.get('conid'))
        evaluate_trading_opportunity(ticker, current_price, close_price_value, conid, logger)
    except (ValueError, TypeError) as e:
        logger.warning(f"{ticker} - Could not evaluate trading opportunity: {e}")


def extract_current_price(ticker: str, market_data_by_ticker: Dict[str, Dict]) -> Optional[float]:
    if ticker not in market_data_by_ticker:
        return None

    parsed_data = market_data_by_ticker[ticker]
    last_price_str = parsed_data.get('last_price')

    if not last_price_str:
        return None

    try:
        return float(last_price_str)
    except (ValueError, TypeError):
        return None


def format_position_with_price(ticker: str, buy_price: float, current_price: float) -> str:
    price_change = current_price - buy_price
    price_change_pct = (price_change / buy_price) * 100
    return f"{ticker} [Buy: ${buy_price:.2f} | Now: ${current_price:.2f} | P/L: {price_change:+.2f} ({price_change_pct:+.2f}%)]"


def format_position_without_price(ticker: str, buy_price: float) -> str:
    return f"{ticker} [Buy: ${buy_price:.2f} | Now: N/A]"


def format_position_detail(ticker: str, position: Dict[str, any], market_data_by_ticker: Dict[str, Dict]) -> str:
    buy_price = position.get("buy_price")
    current_price = extract_current_price(ticker, market_data_by_ticker)

    if current_price:
        return format_position_with_price(ticker, buy_price, current_price)
    else:
        return format_position_without_price(ticker, buy_price)


def has_open_positions() -> bool:
    return len(bought_shares_today) > 0


def log_positions_summary(market_data_by_ticker: Dict[str, Dict], logger: Logger) -> None:
    if not has_open_positions():
        logger.info("CURRENT POSITIONS: None")
        return

    positions_details = [
        format_position_detail(ticker, position, market_data_by_ticker)
        for ticker, position in sorted(bought_shares_today.items())
    ]

    positions_summary = ", ".join(positions_details)
    logger.info(f"CURRENT POSITIONS ({len(bought_shares_today)}): {positions_summary}")


def process_all_companies(companies: List[str], market_data_dir: str, year: int, month: int, day: int, logger: Logger) -> Dict[str, Dict]:
    logger.info(f"Updating market data for {len(companies)} companies...")

    market_data_by_ticker = {}

    for company in companies:
        parsed_data = process_company(company, market_data_dir, year, month, day, logger)
        if parsed_data:
            market_data_by_ticker[company] = parsed_data

    return market_data_by_ticker


def process_company(ticker: str, market_data_dir: str, year: int, month: int, day: int, logger: Logger) -> Optional[Dict]:
    parsed_data = fetch_and_parse_market_data(ticker, logger)
    if parsed_data is None:
        return None

    file_path = f"{market_data_dir}/{ticker}.json"
    existing_closing_price = get_existing_closing_price(file_path, logger)
    closing_price = determine_closing_price(parsed_data, existing_closing_price, logger, ticker)

    evaluate_and_log_trading_opportunity(ticker, parsed_data, closing_price, logger)

    company_data = create_company_data(ticker, parsed_data, closing_price, year, month, day)
    save_company_data(file_path, company_data, logger, ticker)

    return parsed_data


def run_market_data_collection_cycle(s3_client, logger: Logger) -> Optional[Dict[str, Dict]]:
    year, month, day = get_current_date()
    market_data_dir = create_directories(year, month, day)

    settings = download_settings_file(s3_client, S3_BUCKET, logger)
    companies = download_companies_list(s3_client, S3_BUCKET, year, month, day, logger)

    if not has_required_dependencies(settings, companies):
        return None

    market_data_by_ticker = process_all_companies(companies, market_data_dir, year, month, day, logger)

    return market_data_by_ticker


def save_company_data(file_path: str, company_data: Dict, logger: Logger, ticker: str) -> bool:
    try:
        with open(file_path, 'w') as f:
            f.write(dumps(company_data, indent=2))
        logger.info(f"{ticker} - Market data saved to: {file_path}")
        return True
    except Exception as e:
        logger.error(f"{ticker} - Failed to save market data: {e}")
        return False


def sell_at_market_price(ticker: str, logger: Logger) -> None:
    position = bought_shares_today.get(ticker)

    if not position:
        return

    buy_price = position.get("buy_price")
    conid = position.get("conid")
    quantity = position.get("quantity", 1)

    order_result = place_market_sell_order(
        conid=conid,
        quantity=quantity
    )

    if order_result.get("success"):
        bought_shares_today.pop(ticker, None)
        logger.info(f"SELL SUCCESS - {ticker}: {quantity} share(s) at MARKET (bought at ${buy_price:.2f})")
    else:
        error_msg = order_result.get('error', 'Sell order request failed with no error message')
        logger.error(f"SELL FAILED - {ticker}: {error_msg}")


def should_evaluate_trading_opportunity(parsed_data: Dict, closing_price: Optional[str]) -> bool:
    return is_market_open(parsed_data) and closing_price is not None


def should_preserve_existing_closing_price(existing_closing_price: Optional[str]) -> bool:
    return existing_closing_price is not None


def evaluate_trading_opportunity(ticker: str, current_price: float, closing_price: float, conid: int, logger: Logger) -> None:
    price_change_pct = calculate_price_change_percentage(current_price, closing_price)

    if is_price_below_close(price_change_pct):
        log_price_below_close(ticker, current_price, closing_price, price_change_pct, logger)
    elif is_price_above_threshold(price_change_pct):
        log_price_too_high(ticker, current_price, closing_price, price_change_pct, logger)
    elif is_within_buy_range(price_change_pct):
        log_buy_opportunity(ticker, current_price, closing_price, price_change_pct, conid, logger)
    else:
        log_within_range_no_action(ticker, current_price, closing_price, price_change_pct, logger)


def is_close_to_market_close() -> bool:
    current_time = get_current_eastern_time()
    minutes_until_close = calculate_minutes_until_close(current_time)
    return 0 <= minutes_until_close <= MINUTES_BEFORE_CLOSE_TO_SELL


def is_market_open(parsed_data: Dict) -> bool:
    return not parsed_data.get('is_market_closed', True)


def is_price_above_threshold(price_change_pct: float) -> bool:
    return price_change_pct >= 1.0


def is_price_below_close(price_change_pct: float) -> bool:
    return price_change_pct < 0


def is_within_buy_range(price_change_pct: float) -> bool:
    return 0.8 <= price_change_pct <= 0.95


def log_buy_opportunity(ticker: str, current_price: float, closing_price: float, price_change_pct: float, conid: int, logger: Logger) -> None:
    buy_range = format_buy_range(closing_price)
    logger.info(f"BUY OPPORTUNITY - {ticker}: Current ${current_price:.2f} | Close ${closing_price:.2f} {buy_range} | Change +{price_change_pct:.2f}% | Action: READY TO BUY")
    handle_buy_action(ticker, conid, current_price, logger)


def log_price_below_close(ticker: str, current_price: float, closing_price: float, price_change_pct: float, logger: Logger) -> None:
    buy_range = format_buy_range(closing_price)
    logger.info(f"BELOW CLOSE - {ticker}: Current ${current_price:.2f} | Close ${closing_price:.2f} {buy_range} | Change {price_change_pct:.2f}% | Action: WAIT")


def log_price_too_high(ticker: str, current_price: float, closing_price: float, price_change_pct: float, logger: Logger) -> None:
    buy_range = format_buy_range(closing_price)
    logger.info(f"ABOVE THRESHOLD - {ticker}: Current ${current_price:.2f} | Close ${closing_price:.2f} {buy_range} | Change +{price_change_pct:.2f}% | Action: TOO HIGH")


def log_within_range_no_action(ticker: str, current_price: float, closing_price: float, price_change_pct: float, logger: Logger) -> None:
    buy_range = format_buy_range(closing_price)
    logger.info(f"NEUTRAL - {ticker}: Current ${current_price:.2f} | Close ${closing_price:.2f} {buy_range} | Change +{price_change_pct:.2f}% | Action: MONITORING")


def add_position_to_tracking(ticker: str, conid: int, quantity: int, avg_price: float) -> None:
    bought_shares_today[ticker] = {
        "buy_price": avg_price,
        "conid": conid,
        "quantity": quantity
    }


def build_positions_file_path(year: int, month: int, day: int) -> str:
    return f"./files/{year}/{month}/{day}/positions.json"


def load_positions_from_file(file_path: str) -> Dict:
    if not path.exists(file_path):
        return {}

    try:
        with open(file_path, 'r') as f:
            return loads(f.read())
    except Exception:
        return {}


def upload_position_to_s3(file_path: str, s3_client) -> bool:
    try:
        s3_key = "positions.json"
        s3_client.upload_file(file_path, S3_BUCKET, s3_key)
        return True
    except Exception:
        return False


def save_position_to_file(ticker: str, position_data: Dict, year: int, month: int, day: int, s3_client=None) -> bool:
    try:
        file_path = build_positions_file_path(year, month, day)
        positions_file = load_positions_from_file(file_path)

        positions_file[ticker] = {
            "ticker": position_data.get("ticker"),
            "conid": position_data.get("conid"),
            "quantity": position_data.get("position"),
            "average_price": position_data.get("average_price"),
            "market_price": position_data.get("market_price"),
            "market_value": position_data.get("market_value"),
            "unrealized_pnl": position_data.get("unrealized_pnl"),
            "currency": position_data.get("currency"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "date": f"{year}-{month:02d}-{day:02d}"
        }

        with open(file_path, 'w') as f:
            f.write(dumps(positions_file, indent=2))

        if s3_client:
            upload_position_to_s3(file_path, s3_client)

        return True
    except Exception:
        return False


def extract_position_data(position_data: Dict) -> tuple:
    parsed = parse_position(position_data)
    ticker = parsed.get("ticker")
    conid = parsed.get("conid")
    quantity = parsed.get("position")
    avg_price = parsed.get("average_price")
    return ticker, conid, quantity, avg_price


def has_complete_position_data(ticker, conid, quantity, avg_price) -> bool:
    return all([ticker, conid, quantity, avg_price])


def log_fetch_error(error_message: str, logger: Logger) -> None:
    logger.error(f"Failed to fetch positions: {error_message}")


def log_no_positions(logger: Logger) -> None:
    logger.info("No open positions found in IBKR account")


def log_positions_found(count: int, logger: Logger) -> None:
    logger.info(f"Found {count} open position(s) in IBKR account:")


def log_sync_complete(count: int, logger: Logger) -> None:
    logger.info(f"Synced {count} position(s) to local tracking")


def log_sync_start(logger: Logger) -> None:
    logger.info("Fetching current positions from IBKR...")


def sync_position(position_data: Dict, logger: Logger, s3_client=None) -> bool:
    ticker, conid, quantity, avg_price = extract_position_data(position_data)

    if not has_complete_position_data(ticker, conid, quantity, avg_price):
        return False

    add_position_to_tracking(ticker, conid, int(quantity), avg_price)
    logger.info(f"  - {format_position_summary(position_data)}")

    year, month, day = get_current_date()
    parsed = parse_position(position_data)
    save_position_to_file(ticker, parsed, year, month, day, s3_client)

    return True


def fetch_and_sync_positions(logger: Logger, s3_client=None) -> None:
    log_sync_start(logger)

    result = get_all_positions()

    if not result.get("success"):
        log_fetch_error(result.get('error', 'Unknown error'), logger)
        return

    positions = result.get("positions", [])

    if not positions:
        log_no_positions(logger)
        return

    log_positions_found(len(positions), logger)

    for position_data in positions:
        sync_position(position_data, logger, s3_client)

    log_sync_complete(len(bought_shares_today), logger)


if __name__ == "__main__":
    logger = setup_logging(log_file='logs/app.log', log_level=INFO)
    s3_client = client('s3')

    logger.info("Trading application has started successfully.")
    logger.info(f"Market data will update every {UPDATE_INTERVAL} seconds")

    while True:
        fetch_and_sync_positions(logger, s3_client)

        market_data_by_ticker = run_market_data_collection_cycle(s3_client, logger)

        if market_data_by_ticker is not None:
            handle_end_of_day_sales(logger)
            log_positions_summary(market_data_by_ticker, logger)

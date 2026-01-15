from datetime import datetime, timezone
from logging import Logger
from typing import Dict, Optional

from core.state import get_bought_shares, is_files_downloaded, is_ticker_bought
from services.ibkr.ib_gateway_client import get_ib_client
from services.ibkr.ib_market_data_parser import parse_market_data
from trading.buy_orders import handle_buy_action
from utils.file_operations import create_directories, write_json_to_file
from utils.time_utils import get_current_date


def build_company_data_dict(ticker: str, parsed_data: Dict, closing_price: Optional[str], year: int, month: int, day: int) -> Dict:
    return {
        'ticker': ticker,
        'timestamp': get_current_timestamp(),
        'date': format_date(year, month, day),
        'conid': parsed_data.get('conid'),
        'last_price': parsed_data.get('last_price'),
        'closing_price': closing_price,
        'price_difference_from_close': calculate_price_difference_from_close_value(parsed_data.get('last_price'), closing_price),
        'price_change_from_close_pct': calculate_price_change_from_close_percentage(parsed_data.get('last_price'), closing_price),
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


def build_position_summary(ticker: str, buy_price: float, current_price: float, quantity: float) -> tuple:
    pnl = calculate_position_pnl(current_price, buy_price, quantity)
    pnl_pct = calculate_position_pnl_percentage(current_price, buy_price)
    summary = format_position_summary(ticker, buy_price, current_price, pnl, pnl_pct)
    return summary, pnl


def calculate_percentage_change(current: float, base: float) -> float:
    return round(((current - base) / base) * 100, 2)


def calculate_position_pnl(current_price: float, buy_price: float, quantity: float) -> float:
    return (current_price - buy_price) * quantity


def calculate_position_pnl_percentage(current_price: float, buy_price: float) -> float:
    if buy_price == 0:
        return 0.0
    return ((current_price - buy_price) / buy_price) * 100


def calculate_price_change_from_close_percentage(last_price: Optional[str], closing_price: Optional[str]) -> Optional[float]:
    last = parse_price_safely(last_price)
    close = parse_price_safely(closing_price)

    if is_either_price_missing(last, close):
        return None

    return calculate_percentage_change(last, close)


def calculate_price_difference(current: float, base: float) -> float:
    return round(current - base, 2)


def calculate_price_difference_from_close_value(last_price: Optional[str], closing_price: Optional[str]) -> Optional[float]:
    last = parse_price_safely(last_price)
    close = parse_price_safely(closing_price)

    if is_either_price_missing(last, close):
        return None

    return calculate_price_difference(last, close)


def collect_market_data_for_all_companies(companies: list, year: int, month: int, day: int, market_data_dir: str, logger: Logger) -> tuple:
    market_data_by_ticker = {}
    successful_count = 0
    failed_count = 0

    for ticker in companies:
        parsed_data = fetch_market_data_for_ticker(ticker, logger)

        if parsed_data:
            success = process_ticker_data(ticker, parsed_data, year, month, day, market_data_dir, logger)
            if success:
                market_data_by_ticker[ticker] = parsed_data
                successful_count += 1
            else:
                failed_count += 1
        else:
            log_failed_ticker(ticker, logger)
            failed_count += 1

    return market_data_by_ticker, successful_count, failed_count


def determine_order_type(current_price: float, threshold_price: float) -> str:
    return "STOP" if current_price < threshold_price else "LIMIT"


def evaluate_buy_opportunity(ticker: str, current_price: float, closing_price: float, conid: int, logger: Logger) -> None:
    if is_ticker_bought(ticker):
        return

    from utils.calculations import calculate_buy_threshold_price, calculate_price_change_percentage

    threshold_price = calculate_buy_threshold_price(closing_price)
    price_change_pct = calculate_price_change_percentage(current_price, closing_price)
    order_type = determine_order_type(current_price, threshold_price)

    log_buy_setup(ticker, current_price, threshold_price, closing_price, price_change_pct, order_type, logger)
    handle_buy_action(ticker, conid, current_price, closing_price, logger)


def evaluate_trading_for_ticker(ticker: str, parsed_data: Dict, closing_price: Optional[str], logger: Logger) -> None:
    if not should_evaluate_trading(parsed_data, closing_price):
        return

    current_price = parsed_data.get('last_price')
    conid = parsed_data.get('conid')

    if has_required_trading_data(current_price, conid):
        evaluate_buy_opportunity(ticker, current_price, float(closing_price), conid, logger)


def fetch_market_data_for_ticker(ticker: str, logger: Logger) -> Optional[Dict]:
    ib_client = get_ib_client()

    try:
        market_data = ib_client.get_market_data(ticker)

        if not market_data:
            log_no_market_data(ticker, logger)
            return None

        parsed_data = parse_market_data(market_data)
        log_market_data(ticker, parsed_data, logger)

        return parsed_data

    except Exception as e:
        log_market_data_error(ticker, e, logger)
        return None


def format_date(year: int, month: int, day: int) -> str:
    return f"{year}-{month:02d}-{day:02d}"


def format_position_summary(ticker: str, buy_price: float, current_price: float, pnl: float, pnl_pct: float) -> str:
    return f"{ticker} [Buy: ${buy_price:.2f} | Now: ${current_price:.2f} | P/L: {pnl:+.2f} ({pnl_pct:+.2f}%)]"


def get_cached_settings_and_companies():
    import core.state as state
    return state.cached_settings, state.cached_companies


def get_current_price_for_ticker(ticker: str, market_data_by_ticker: Dict, buy_price: float) -> float:
    current_data = market_data_by_ticker.get(ticker, {})
    return current_data.get('last_price', buy_price)


def get_current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_position_data(ticker: str, share_data: Dict, market_data_by_ticker: Dict) -> tuple:
    buy_price = share_data.get('buy_price', 0)
    quantity = share_data.get('quantity', 0)
    current_price = get_current_price_for_ticker(ticker, market_data_by_ticker, buy_price)
    return buy_price, quantity, current_price


def has_positions() -> bool:
    return len(get_bought_shares()) > 0


def has_required_trading_data(current_price: Optional[float], conid: Optional[int]) -> bool:
    return current_price is not None and conid is not None


def is_either_price_missing(price1: Optional[float], price2: Optional[float]) -> bool:
    return price1 is None or price2 is None


def is_market_open(parsed_data: Dict) -> bool:
    return not parsed_data.get('is_market_closed', True)


def is_prerequisites_satisfied(logger: Logger) -> bool:
    if not is_files_downloaded():
        logger.warning("Daily files not yet downloaded - skipping market data collection")
        return False

    settings, companies = get_cached_settings_and_companies()
    if settings is None or companies is None:
        logger.warning("Settings or companies not cached - skipping market data collection")
        return False

    return True


def log_buy_setup(ticker: str, current_price: float, threshold_price: float, closing_price: float, price_change_pct: float, order_type: str, logger: Logger) -> None:
    logger.info(
        f"BUY SETUP - {ticker}: Current ${current_price:.2f} {'<' if order_type == 'STOP' else '>='} "
        f"Threshold ${threshold_price:.2f} | Close ${closing_price:.2f} | "
        f"Change {price_change_pct:+.2f}% | Using BUY {order_type} order"
    )


def log_collection_complete(successful_count: int, failed_count: int, logger: Logger) -> None:
    logger.info(f"Market data collection complete: {successful_count} successful, {failed_count} failed")


def log_collection_start(company_count: int, logger: Logger) -> None:
    logger.info(f"Processing {company_count} companies for market data...")


def log_failed_ticker(ticker: str, logger: Logger) -> None:
    logger.error(f"{ticker} - Failed to fetch market data, skipping")


def log_limited_data_warning(ticker: str, last_price, bid_price, ask_price, logger: Logger) -> None:
    logger.warning(f"{ticker} - Limited data: Last=${last_price}, Bid=${bid_price}, Ask=${ask_price}")
    logger.warning(f"{ticker} - This may indicate IBKR market data subscription issue or ticker not found")


def log_market_data(ticker: str, parsed_data: Dict, logger: Logger) -> None:
    last_price = parsed_data.get('last_price')
    bid_price = parsed_data.get('bid_price')
    ask_price = parsed_data.get('ask_price')
    spread_percent = parsed_data.get('spread_percent', 0)

    if last_price and bid_price and ask_price:
        logger.info(f"{ticker} - Price: ${last_price:.2f}, Bid: ${bid_price:.2f}, Ask: ${ask_price:.2f}, Spread: {spread_percent:.2f}%")
    else:
        log_limited_data_warning(ticker, last_price, bid_price, ask_price, logger)


def log_market_data_error(ticker: str, error: Exception, logger: Logger) -> None:
    logger.error(f"{ticker} - Error fetching market data: {error}")
    import traceback
    logger.error(f"{ticker} - Traceback: {traceback.format_exc()}")


def log_no_market_data(ticker: str, logger: Logger) -> None:
    logger.warning(f"{ticker} - No market data available from IBKR")


def log_positions_summary(market_data_by_ticker: Dict[str, Dict], logger: Logger) -> None:
    if not has_positions():
        return

    position_summaries, total_pnl = summarize_all_positions(market_data_by_ticker)
    log_positions_details(position_summaries, total_pnl, logger)


def log_positions_details(position_summaries: list, total_pnl: float, logger: Logger) -> None:
    logger.info(f"CURRENT POSITIONS ({len(position_summaries)}): {', '.join(position_summaries)}")
    logger.info(f"Total P/L: ${total_pnl:+.2f}")


def log_skipping_trading_evaluation(ticker: str, logger: Logger) -> None:
    logger.warning(f"{ticker} - Skipping trading evaluation: No price data available")


def parse_price_safely(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def process_ticker_data(ticker: str, parsed_data: Dict, year: int, month: int, day: int, market_data_dir: str, logger: Logger) -> bool:
    closing_price = parsed_data.get('closing_price')
    last_price = parsed_data.get('last_price')

    if last_price:
        evaluate_trading_for_ticker(ticker, parsed_data, closing_price, logger)
        save_ticker_market_data(ticker, parsed_data, closing_price, year, month, day, market_data_dir, logger)
        return True
    else:
        log_skipping_trading_evaluation(ticker, logger)
        save_ticker_market_data(ticker, parsed_data, closing_price, year, month, day, market_data_dir, logger)
        return False


def run_market_data_collection_cycle(s3_client, logger: Logger) -> Optional[Dict[str, Dict]]:
    if not is_prerequisites_satisfied(logger):
        return None

    year, month, day = get_current_date()
    market_data_dir = create_directories(year, month, day)

    import core.state as state
    companies = state.cached_companies

    log_collection_start(len(companies), logger)
    market_data_by_ticker, successful_count, failed_count = collect_market_data_for_all_companies(
        companies, year, month, day, market_data_dir, logger
    )
    log_collection_complete(successful_count, failed_count, logger)

    return market_data_by_ticker if market_data_by_ticker else None


def save_ticker_market_data(ticker: str, parsed_data: Dict, closing_price: Optional[str], year: int, month: int, day: int, market_data_dir: str, logger: Logger) -> bool:
    file_path = f"{market_data_dir}/{ticker}.json"
    company_data = build_company_data_dict(ticker, parsed_data, closing_price, year, month, day)

    try:
        write_json_to_file(file_path, company_data)
        logger.info(f"{ticker} - Market data saved to: {file_path}")
        return True
    except Exception as e:
        logger.error(f"{ticker} - Failed to save market data: {e}")
        return False


def should_evaluate_trading(parsed_data: Dict, closing_price: Optional[str]) -> bool:
    return is_market_open(parsed_data) and closing_price is not None


def summarize_all_positions(market_data_by_ticker: Dict) -> tuple:
    bought_shares = get_bought_shares()
    position_summaries = []
    total_pnl = 0.0

    for ticker, share_data in bought_shares.items():
        buy_price, quantity, current_price = get_position_data(ticker, share_data, market_data_by_ticker)
        summary, pnl = build_position_summary(ticker, buy_price, current_price, quantity)
        position_summaries.append(summary)
        total_pnl += pnl

    return position_summaries, total_pnl



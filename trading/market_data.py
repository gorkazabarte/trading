"""
Market data collection and processing.
"""
from typing import Dict, Optional
from logging import Logger
from datetime import datetime, timezone

from utils.file_operations import create_directories
from core.state import is_files_downloaded, get_bought_shares
from utils.time_utils import get_current_date
from trading.buy_orders import handle_buy_action
from services.ibkr.ib_gateway_client import get_ib_client
from services.ibkr.ib_market_data_parser import parse_market_data


def parse_float_safely(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def calculate_percentage_change(current: float, base: float) -> float:
    return round(((current - base) / base) * 100, 2)


def calculate_price_difference(current: float, base: float) -> float:
    return round(current - base, 2)


def calculate_price_change_from_close(last_price: Optional[str], closing_price: Optional[str]) -> Optional[float]:
    last = parse_float_safely(last_price)
    close = parse_float_safely(closing_price)

    if last is None or close is None:
        return None

    return calculate_percentage_change(last, close)


def calculate_price_difference_from_close(last_price: Optional[str], closing_price: Optional[str]) -> Optional[float]:
    last = parse_float_safely(last_price)
    close = parse_float_safely(closing_price)

    if last is None or close is None:
        return None

    return calculate_price_difference(last, close)


def fetch_market_data_for_ticker(ticker: str, logger: Logger):
    ib_client = get_ib_client()

    try:
        market_data = ib_client.get_market_data(ticker)

        if not market_data:
            logger.warning(f"{ticker} - No market data available")
            return None

        parsed_data = parse_market_data(market_data)

        last_price = parsed_data.get('last_price')
        bid_price = parsed_data.get('bid_price')
        ask_price = parsed_data.get('ask_price')
        spread_percent = parsed_data.get('spread_percent', 0)

        if last_price and bid_price and ask_price:
            logger.info(f"{ticker} - Price: ${last_price:.2f}, Bid: ${bid_price:.2f}, Ask: ${ask_price:.2f}, Spread: {spread_percent:.2f}%")
        else:
            logger.info(f"{ticker} - Limited data: Last=${last_price}, Bid=${bid_price}, Ask=${ask_price}")

        return parsed_data

    except Exception as e:
        logger.error(f"{ticker} - Error fetching market data: {e}")
        return None


def should_evaluate_trading_opportunity(parsed_data: Dict, closing_price: Optional[str]) -> bool:
    is_market_open = not parsed_data.get('is_market_closed', True)
    return is_market_open and closing_price is not None


def evaluate_trading_opportunity(ticker: str, current_price: float, closing_price: float, conid: int, logger: Logger) -> None:
    from core.state import is_ticker_bought

    if is_ticker_bought(ticker):
        return

    from utils.calculations import calculate_buy_threshold_price, calculate_price_change_percentage

    threshold_price = calculate_buy_threshold_price(closing_price)
    price_change_pct = calculate_price_change_percentage(current_price, closing_price)

    if current_price < threshold_price:
        order_type = "STOP"
        logger.info(f"BUY SETUP - {ticker}: Current ${current_price:.2f} < Threshold ${threshold_price:.2f} | Close ${closing_price:.2f} | Change {price_change_pct:+.2f}% | Using BUY {order_type} order")
    else:
        order_type = "LIMIT"
        logger.info(f"BUY SETUP - {ticker}: Current ${current_price:.2f} >= Threshold ${threshold_price:.2f} | Close ${closing_price:.2f} | Change {price_change_pct:+.2f}% | Using BUY {order_type} order")

    handle_buy_action(ticker, conid, current_price, closing_price, logger)


def is_spread_acceptable(spread_percent: Optional[float]) -> bool:
    return spread_percent is not None and spread_percent < 0.5


def evaluate_and_log_trading_opportunity(ticker: str, parsed_data: Dict, closing_price: Optional[str], logger: Logger) -> None:
    if not should_evaluate_trading_opportunity(parsed_data, closing_price):
        return

    spread_percent = parsed_data.get('spread_percent')

    if not is_spread_acceptable(spread_percent):
        logger.info(f"{ticker} - Spread too high ({spread_percent}%), skipping buy.")
        return

    current_price = parsed_data.get('last_price')
    conid = parsed_data.get('conid')

    if current_price and conid:
        evaluate_trading_opportunity(ticker, current_price, float(closing_price), conid, logger)


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


def save_company_data(file_path: str, company_data: Dict, logger: Logger, ticker: str) -> bool:
    from utils.file_operations import write_json_to_file

    try:
        write_json_to_file(file_path, company_data)
        logger.info(f"{ticker} - Market data saved to: {file_path}")
        return True
    except Exception as e:
        logger.error(f"{ticker} - Failed to save market data: {e}")
        return False


def run_market_data_collection_cycle(s3_client, logger: Logger) -> Optional[Dict[str, Dict]]:
    import core.state as state

    year, month, day = get_current_date()
    market_data_dir = create_directories(year, month, day)

    if not is_files_downloaded() or state.cached_settings is None or state.cached_companies is None:
        logger.warning("Daily files not yet downloaded - skipping market data collection")
        return None

    market_data_by_ticker = {}

    for ticker in state.cached_companies:
        parsed_data = fetch_market_data_for_ticker(ticker, logger)

        if parsed_data:
            closing_price = parsed_data.get('closing_price')

            if is_spread_acceptable(parsed_data.get('spread_percent')):
                evaluate_and_log_trading_opportunity(ticker, parsed_data, closing_price, logger)

            file_path = f"{market_data_dir}/{ticker}.json"
            company_data = create_company_data(ticker, parsed_data, closing_price, year, month, day)
            save_company_data(file_path, company_data, logger, ticker)

            market_data_by_ticker[ticker] = parsed_data

    return market_data_by_ticker


def log_positions_summary(market_data_by_ticker: Dict[str, Dict], logger: Logger) -> None:
    bought_shares = get_bought_shares()

    if not bought_shares:
        return

    position_summaries = []
    total_pnl = 0.0

    for ticker, share_data in bought_shares.items():
        buy_price = share_data.get('buy_price', 0)
        quantity = share_data.get('quantity', 0)

        current_data = market_data_by_ticker.get(ticker, {})
        current_price = current_data.get('last_price', buy_price)

        pnl = (current_price - buy_price) * quantity
        pnl_pct = ((current_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0

        total_pnl += pnl

        position_summaries.append(
            f"{ticker} [Buy: ${buy_price:.2f} | Now: ${current_price:.2f} | P/L: {pnl:+.2f} ({pnl_pct:+.2f}%)]"
        )

    logger.info(f"CURRENT POSITIONS ({len(bought_shares)}): {', '.join(position_summaries)}")
    logger.info(f"Total P/L: ${total_pnl:+.2f}")


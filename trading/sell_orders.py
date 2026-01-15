from typing import List, Dict
from logging import Logger

from utils.time_utils import is_close_to_market_close, get_current_date_string
from core.state import get_share_data, remove_bought_share, add_closed_position
from services.ibkr.ib_gateway_client import get_ib_client
from services.ibkr.ib_portfolio import clear_open_positions


def can_close_position(ticker: str, quantity: float) -> bool:
    return ticker is not None and quantity is not None and quantity > 0


def has_positions(positions: List) -> bool:
    return positions and len(positions) > 0


def is_connected(ib_client) -> bool:
    return ib_client.connected


def log_closing_all_positions(logger: Logger) -> None:
    logger.info("=" * 60)
    logger.info("MARKET CLOSING SOON - Closing all open positions")
    logger.info("=" * 60)


def log_closing_complete(logger: Logger) -> None:
    logger.info("=" * 60)


def log_no_positions(logger: Logger) -> None:
    logger.info("No open positions to close")


def log_position_count(count: int, logger: Logger) -> None:
    logger.info(f"Found {count} open position(s) to close:")


def log_position_closing(ticker: str, quantity: float, avg_price: float, market_price: float, logger: Logger) -> None:
    logger.info(f"  Closing {ticker}: {quantity} shares @ avg ${avg_price:.2f} (Market: ${market_price:.2f})")


def extract_position_info(position_data: Dict) -> tuple:
    ticker = position_data.get('ticker')
    quantity = position_data.get('position')
    avg_price = position_data.get('average_price')
    market_price = position_data.get('market_price', avg_price)
    return ticker, quantity, avg_price, market_price


def execute_market_sell(ib_client, ticker: str, quantity: int):
    return ib_client.place_market_order(
        ticker=ticker,
        quantity=quantity,
        action='SELL'
    )


def get_buy_date(ticker: str) -> str:
    position_info = get_share_data(ticker)
    return position_info.get("buy_date") if position_info else get_current_date_string()


def calculate_profit(sell_price: float, buy_price: float, quantity: int) -> float:
    return (sell_price - buy_price) * quantity


def calculate_return_percentage(sell_price: float, buy_price: float) -> float:
    return ((sell_price - buy_price) / buy_price) * 100


def build_closed_position(ticker: str, buy_date: str, buy_price: float, sell_price: float, quantity: int) -> Dict:
    profit = calculate_profit(sell_price, buy_price, quantity)
    return_pct = calculate_return_percentage(sell_price, buy_price)
    sell_date = get_current_date_string()

    return {
        "symbol": ticker,
        "buy_date": buy_date,
        "sell_date": sell_date,
        "buy_price": round(buy_price, 2),
        "sell_price": round(sell_price, 2),
        "quantity": quantity,
        "profit": round(profit, 2),
        "return_pct": round(return_pct, 2)
    }


def save_closed_position(closed_position: Dict, ticker: str) -> None:
    add_closed_position(closed_position)
    remove_bought_share(ticker)


def log_successful_sell(ticker: str, quantity: float, buy_price: float, sell_price: float, closed_position: Dict, logger: Logger) -> None:
    logger.info(f"SELL SUCCESS - {ticker}: {quantity} share(s) at MARKET | Bought: ${buy_price:.2f} | Sold: ${sell_price:.2f} | P/L: ${closed_position['profit']:.2f} ({closed_position['return_pct']:.2f}%)")


def log_failed_sell(ticker: str, error_msg: str, logger: Logger) -> None:
    logger.error(f"SELL FAILED - {ticker}: {error_msg}")


def process_successful_sell(ticker: str, quantity: float, buy_price: float, sell_price: float, logger: Logger) -> None:
    buy_date = get_buy_date(ticker)
    closed_position = build_closed_position(ticker, buy_date, buy_price, sell_price, int(quantity))
    save_closed_position(closed_position, ticker)
    log_successful_sell(ticker, quantity, buy_price, sell_price, closed_position, logger)


def sell_at_market_price(ticker: str, quantity: float, buy_price: float, sell_price: float, logger: Logger) -> None:
    try:
        ib_client = get_ib_client()

        if not ib_client or not ib_client.connected:
            logger.error(f"SELL FAILED - {ticker}: IB Gateway not connected")
            return

        order_result = execute_market_sell(ib_client, ticker, int(quantity))

        if order_result.get("success"):
            process_successful_sell(ticker, quantity, buy_price, sell_price, logger)
        else:
            error_msg = order_result.get('error', 'Sell order request failed')
            log_failed_sell(ticker, error_msg, logger)
    except Exception as e:
        logger.error(f"SELL FAILED - {ticker}: Exception occurred: {e}")


def close_position(position_data: Dict, logger: Logger) -> bool:
    try:
        ticker, quantity, avg_price, market_price = extract_position_info(position_data)

        if not can_close_position(ticker, quantity):
            return False

        log_position_closing(ticker, quantity, avg_price, market_price, logger)
        sell_at_market_price(ticker, quantity, avg_price, market_price, logger)
        return True
    except Exception as e:
        ticker = position_data.get('ticker', 'UNKNOWN')
        logger.error(f"Exception while closing position for {ticker}: {e}")
        return False


def cancel_all_pending_orders(ib_client, s3_client, logger) -> None:
    cancel_result = ib_client.cancel_all_orders()

    if not cancel_result.get('success'):
        logger.error(f"Failed to cancel orders: {cancel_result.get('error', 'Unknown error')}")
        return

    cancelled_count = cancel_result.get('cancelled_count', 0)

    if cancelled_count > 0:
        logger.info(f"Cancelled {cancelled_count} pending order(s)")
        clear_open_positions(s3_client, logger)
    else:
        logger.info("No pending orders to cancel")


def close_positions(positions: List, logger: Logger) -> None:
    from time import sleep

    log_position_count(len(positions), logger)

    closed_count = 0
    failed_count = 0

    for idx, position_data in enumerate(positions):
        ticker = position_data.get('ticker', 'UNKNOWN')
        logger.info(f"Processing position {idx + 1}/{len(positions)}: {ticker}")

        success = close_position(position_data, logger)
        if success:
            closed_count += 1
        else:
            failed_count += 1

        if idx < len(positions) - 1:
            logger.info(f"Waiting 1 second before processing next position...")
            sleep(1)

    logger.info(f"Position closing complete: {closed_count} closed, {failed_count} failed or skipped")


def should_close_positions() -> bool:
    return is_close_to_market_close()


def connect_to_ib(logger: Logger):
    ib_client = get_ib_client()

    if not is_connected(ib_client):
        logger.error("IB Gateway not connected - cannot close positions")
        return None

    return ib_client


def no_positions_exist(positions: List, logger: Logger) -> bool:
    if not has_positions(positions):
        log_no_positions(logger)
        return True
    return False


def handle_end_of_day_sales(logger: Logger, s3_client) -> None:
    from core.state import set_closing_phase

    if not should_close_positions():
        return

    set_closing_phase()

    log_closing_all_positions(logger)

    ib_client = connect_to_ib(logger)
    if not ib_client:
        return

    cancel_all_pending_orders(ib_client, s3_client, logger)

    positions = ib_client.get_positions()

    if no_positions_exist(positions, logger):
        log_closing_complete(logger)
        return

    close_positions(positions, logger)
    log_closing_complete(logger)

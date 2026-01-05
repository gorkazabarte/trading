"""
Sell order execution and end-of-day position closing.
"""
from typing import List, Dict
from logging import Logger

from utils.time_utils import is_close_to_market_close, get_current_date_string
from core.state import get_share_data, remove_bought_share, add_closed_position
from services.ibkr.ib_gateway_client import get_ib_client


def is_ib_client_connected(ib_client) -> bool:
    return ib_client.connected


def has_valid_positions(positions: List) -> bool:
    return positions and len(positions) > 0


def is_valid_position_to_close(ticker: str, quantity: float) -> bool:
    return ticker is not None and quantity is not None and quantity > 0


def log_market_closing_header(logger: Logger) -> None:
    logger.info("=" * 60)
    logger.info("MARKET CLOSING SOON - Closing all open positions")
    logger.info("=" * 60)


def log_market_closing_footer(logger: Logger) -> None:
    logger.info("=" * 60)


def log_no_positions_to_close(logger: Logger) -> None:
    logger.info("No open positions to close")


def log_positions_count(count: int, logger: Logger) -> None:
    logger.info(f"Found {count} open position(s) to close:")


def log_closing_position(ticker: str, quantity: float, avg_price: float, market_price: float, logger: Logger) -> None:
    logger.info(f"  Closing {ticker}: {quantity} shares @ avg ${avg_price:.2f} (Market: ${market_price:.2f})")


def get_position_details(position_data: Dict) -> tuple:
    ticker = position_data.get('ticker')
    quantity = position_data.get('position')
    avg_price = position_data.get('average_price')
    market_price = position_data.get('market_price', avg_price)
    return ticker, quantity, avg_price, market_price


def place_market_sell_order(ib_client, ticker: str, quantity: int):
    return ib_client.place_market_order(
        ticker=ticker,
        quantity=quantity,
        action='SELL'
    )


def get_buy_date_for_position(ticker: str) -> str:
    position_info = get_share_data(ticker)
    return position_info.get("buy_date") if position_info else get_current_date_string()


def create_closed_position_entry(ticker: str, buy_date: str, buy_price: float, sell_price: float, quantity: int) -> Dict:
    profit = (sell_price - buy_price) * quantity
    return_pct = ((sell_price - buy_price) / buy_price) * 100

    return {
        "symbol": ticker,
        "buy_date": buy_date,
        "buy_price": round(buy_price, 2),
        "sell_price": round(sell_price, 2),
        "quantity": quantity,
        "profit": round(profit, 2),
        "return_pct": round(return_pct, 2)
    }


def record_closed_position(closed_position: Dict, ticker: str) -> None:
    add_closed_position(closed_position)
    remove_bought_share(ticker)


def log_sell_success(ticker: str, quantity: float, buy_price: float, sell_price: float, closed_position: Dict, logger: Logger) -> None:
    logger.info(f"SELL SUCCESS - {ticker}: {quantity} share(s) at MARKET | Bought: ${buy_price:.2f} | Sold: ${sell_price:.2f} | P/L: ${closed_position['profit']:.2f} ({closed_position['return_pct']:.2f}%)")


def log_sell_failure(ticker: str, error_msg: str, logger: Logger) -> None:
    logger.error(f"SELL FAILED - {ticker}: {error_msg}")


def sell_position_at_market(ticker: str, quantity: float, buy_price: float, sell_price: float, logger: Logger) -> None:
    ib_client = get_ib_client()
    order_result = place_market_sell_order(ib_client, ticker, int(quantity))

    if order_result.get("success"):
        buy_date = get_buy_date_for_position(ticker)
        closed_position = create_closed_position_entry(
            ticker=ticker,
            buy_date=buy_date,
            buy_price=buy_price,
            sell_price=sell_price,
            quantity=int(quantity)
        )

        record_closed_position(closed_position, ticker)
        log_sell_success(ticker, quantity, buy_price, sell_price, closed_position, logger)
    else:
        error_msg = order_result.get('error', 'Sell order request failed')
        log_sell_failure(ticker, error_msg, logger)


def close_single_position(position_data: Dict, logger: Logger) -> None:
    ticker, quantity, avg_price, market_price = get_position_details(position_data)

    if not is_valid_position_to_close(ticker, quantity):
        return

    log_closing_position(ticker, quantity, avg_price, market_price, logger)
    sell_position_at_market(ticker, quantity, avg_price, market_price, logger)


def close_all_positions(positions: List, logger: Logger) -> None:
    log_positions_count(len(positions), logger)

    for position_data in positions:
        close_single_position(position_data, logger)


def handle_end_of_day_sales(logger: Logger) -> None:
    if not is_close_to_market_close():
        return

    log_market_closing_header(logger)

    ib_client = get_ib_client()

    if not is_ib_client_connected(ib_client):
        logger.error("IB Gateway not connected - cannot close positions")
        return

    positions = ib_client.get_positions()

    if not has_valid_positions(positions):
        log_no_positions_to_close(logger)
        return

    close_all_positions(positions, logger)
    log_market_closing_footer(logger)


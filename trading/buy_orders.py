"""
Buy order execution and management.
"""
from typing import Dict, Optional
from logging import Logger

from utils.calculations import (
    calculate_buy_threshold_price,
    calculate_budget_per_trade,
    calculate_quantity_from_budget,
    calculate_stop_loss_price,
    calculate_take_profit_price
)
from utils.time_utils import get_current_date, get_current_date_string
from core.state import is_ticker_bought, add_bought_share
from utils.aws_client import create_s3_client
from services.ibkr.ib_gateway_client import get_ib_client


def calculate_order_parameters(threshold_price: float, logger: Logger, ticker: str) -> Optional[Dict]:
    budget_per_trade = calculate_budget_per_trade()
    quantity = calculate_quantity_from_budget(threshold_price)

    if quantity == 0:
        logger.warning(f"SKIP - {ticker}: Budget ${budget_per_trade:.2f} insufficient for threshold price ${threshold_price:.2f}")
        return None

    return {
        'quantity': quantity,
        'budget': budget_per_trade,
        'estimated_cost': quantity * threshold_price,
        'stop_loss_price': calculate_stop_loss_price(threshold_price),
        'take_profit_price': calculate_take_profit_price(threshold_price)
    }


def log_order_calculation(ticker: str, params: Dict, threshold_price: float, logger: Logger) -> None:
    logger.info(f"ORDER CALCULATION - {ticker}: Budget=${params['budget']:.2f} | Threshold=${threshold_price:.2f} | Quantity={params['quantity']} shares | Total=${params['estimated_cost']:.2f}")


def should_use_stop_order(current_price: float, threshold_price: float) -> bool:
    return current_price < threshold_price


def place_stop_bracket_order_for_ticker(ib_client, ticker: str, params: Dict, threshold_price: float):
    return ib_client.place_stop_bracket_order(
        ticker=ticker,
        quantity=params['quantity'],
        stop_price=threshold_price,
        stop_loss_price=params['stop_loss_price'],
        take_profit_price=params['take_profit_price']
    )


def place_limit_bracket_order_for_ticker(ib_client, ticker: str, params: Dict, threshold_price: float):
    return ib_client.place_limit_bracket_order(
        ticker=ticker,
        quantity=params['quantity'],
        limit_price=threshold_price,
        stop_loss_price=params['stop_loss_price'],
        take_profit_price=params['take_profit_price']
    )


def execute_bracket_order(ib_client, ticker: str, current_price: float, threshold_price: float, params: Dict):
    if should_use_stop_order(current_price, threshold_price):
        order_result = place_stop_bracket_order_for_ticker(ib_client, ticker, params, threshold_price)
        return order_result, "STOP", f"Stop @ ${threshold_price:.2f}"
    else:
        order_result = place_limit_bracket_order_for_ticker(ib_client, ticker, params, threshold_price)
        return order_result, "LIMIT", f"Limit @ ${threshold_price:.2f}"


def record_bought_share(ticker: str, conid: int, threshold_price: float, params: Dict, order_type: str) -> None:
    buy_date = get_current_date_string()
    share_data = {
        "buy_price": threshold_price,
        "buy_date": buy_date,
        "conid": conid,
        "quantity": params['quantity'],
        "stop_loss_price": params['stop_loss_price'],
        "take_profit_price": params['take_profit_price'],
        "order_type": order_type
    }
    add_bought_share(ticker, share_data)


def create_position_data(ticker: str, conid: int, params: Dict, threshold_price: float, current_price: float, order_type: str, order_status: str = "PENDING", filled: bool = False) -> Dict:
    return {
        "ticker": ticker,
        "conid": conid,
        "position": params['quantity'],
        "average_price": threshold_price,
        "market_price": current_price,
        "market_value": current_price * params['quantity'],
        "unrealized_pnl": 0.0,
        "currency": "USD",
        "order_type": order_type,
        "order_price": threshold_price,
        "order_status": order_status,
        "filled": filled,
        "stop_loss_price": params['stop_loss_price'],
        "take_profit_price": params['take_profit_price']
    }


def log_buy_success(ticker: str, order_type: str, params: Dict, entry_price_desc: str, current_price: float, logger: Logger) -> None:
    logger.info(f"BUY {order_type} - {ticker}: {params['quantity']} share(s) {entry_price_desc} (Current: ${current_price:.2f}, Est: ${params['estimated_cost']:.2f}) | Stop Loss: ${params['stop_loss_price']:.2f} | Take Profit: ${params['take_profit_price']:.2f}")


def log_buy_failure(ticker: str, order_type: str, error_msg: str, logger: Logger) -> None:
    logger.error(f"BUY {order_type} FAILED - {ticker}: {error_msg}")


def save_position_to_file(ticker: str, position_data: Dict, year: int, month: int, day: int, s3_client) -> None:
    from services.ibkr.ib_portfolio import load_open_positions, open_positions_file_exists, save_positions_to_files

    # Load existing positions (if any)
    existing_positions = {}
    if open_positions_file_exists():
        existing_positions = load_open_positions() or {}

    # Add/update this ticker's position
    existing_positions[ticker] = position_data

    # Save all positions
    save_positions_to_files(existing_positions, year, month, day, s3_client)


def handle_buy_action(ticker: str, conid: int, current_price: float, closing_price: float, logger: Logger) -> None:
    if is_ticker_bought(ticker):
        return

    threshold_price = calculate_buy_threshold_price(closing_price)
    params = calculate_order_parameters(threshold_price, logger, ticker)

    if params is None:
        return

    log_order_calculation(ticker, params, threshold_price, logger)

    ib_client = get_ib_client()
    order_result, order_type, entry_price_desc = execute_bracket_order(
        ib_client, ticker, current_price, threshold_price, params
    )

    if order_result.get("success"):
        record_bought_share(ticker, conid, threshold_price, params, order_type)
        log_buy_success(ticker, order_type, params, entry_price_desc, current_price, logger)

        year, month, day = get_current_date()
        position_data = create_position_data(ticker, conid, params, threshold_price, current_price, order_type, "PENDING", filled=False)
        s3_client = create_s3_client()
        save_position_to_file(ticker, position_data, year, month, day, s3_client)
        logger.info(f"{ticker} - Pending order saved to open_positions.json")
    else:
        error_msg = order_result.get('error', 'Order request failed with no error message')
        log_buy_failure(ticker, order_type, error_msg, logger)


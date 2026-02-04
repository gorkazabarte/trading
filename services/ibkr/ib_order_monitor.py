"""
Monitor IBKR orders and detect when bracket orders (Stop Loss or Take Profit) are filled.

This module continuously monitors open positions and detects when bracket orders
(Stop Loss or Take Profit) are executed by IBKR. When detected:

1. Immediately creates a closed position record with accurate execution prices
2. Calculates profit/loss and return percentage
3. Identifies whether exit was via STOP_LOSS or TAKE_PROFIT
4. Removes the position from open_positions.json
5. Saves the closed position to closed_positions.json for the day

This ensures real-time tracking of all position exits without waiting for
end-of-day reconciliation.
"""
from logging import Logger
from typing import Dict, List, Optional, Set


def detect_bracket_fills(logger: Logger, s3_client) -> None:
    """
    Main function to detect and process filled bracket orders.
    """
    from services.ibkr.ib_gateway_client import get_ib_client

    ib_client = get_ib_client()
    if not ib_client.connected:
        return

    open_positions = load_open_positions_safely()
    if not open_positions:
        return

    filled_tickers = get_filled_tickers(open_positions)
    if not filled_tickers:
        return

    executions = ib_client.get_todays_executions()
    if not executions:
        return

    process_executions_for_bracket_fills(
        executions, filled_tickers, open_positions, logger, s3_client
    )


def extract_sell_execution_data(sell_execution: Dict) -> Dict:
    """
    Extract relevant data from a sell execution.
    """
    return {
        'ticker': sell_execution['ticker'],
        'sell_price': sell_execution['price'],
        'sell_time': sell_execution['time'],
        'shares': sell_execution['shares']
    }


def get_filled_tickers(open_positions: Dict) -> Set[str]:
    """
    Get tickers that have filled BUY orders.
    """
    return {
        ticker for ticker, pos in open_positions.items()
        if pos.get('filled', False)
    }


def is_bracket_order_fill(ticker: str, execution: Dict, filled_tickers: Set[str]) -> bool:
    """
    Check if an execution represents a bracket order fill (Stop Loss or Take Profit).
    """
    return (
        execution['ticker'] == ticker and
        execution['side'] in ['SLD', 'SELL'] and
        ticker in filled_tickers
    )


def load_open_positions_safely() -> Dict:
    """
    Safely load open positions, returning empty dict if file doesn't exist.
    """
    from services.ibkr.ib_portfolio import open_positions_file_exists, load_open_positions

    if not open_positions_file_exists():
        return {}

    try:
        return load_open_positions()
    except Exception:
        return {}


def process_bracket_order_fill(ticker: str, position_data: Dict, sell_data: Dict,
                               logger: Logger, s3_client) -> None:
    """
    Process a filled bracket order and create a closed position record.
    """
    from core.state import add_closed_position, remove_bought_share
    from utils.time_utils import get_current_date
    from workflow.reconciliation import save_closed_positions_if_exist

    buy_price = position_data.get('average_price', position_data.get('order_price', 0))
    sell_price = sell_data['sell_price']
    quantity = position_data.get('position', sell_data['shares'])

    profit = round((sell_price - buy_price) * quantity, 2)
    return_pct = round(((sell_price - buy_price) / buy_price * 100), 2) if buy_price > 0 else 0.0

    year, month, day = get_current_date()

    closed_position = {
        'symbol': ticker,
        'buy_date': f"{year}-{month:02d}-{day:02d}",
        'sell_date': f"{year}-{month:02d}-{day:02d}",
        'buy_price': round(buy_price, 2),
        'sell_price': round(sell_price, 2),
        'quantity': int(quantity),
        'profit': profit,
        'return_pct': return_pct,
        'exit_type': resolve_exit_type(sell_price, position_data)
    }

    add_closed_position(closed_position)
    remove_bought_share(ticker)

    logger.info(f"POSITION CLOSED - {ticker}: Bought @ ${buy_price:.2f}, "
                f"Sold @ ${sell_price:.2f}, P/L: ${profit:.2f} ({return_pct:.2f}%) "
                f"via {closed_position['exit_type']}")

    remove_ticker_from_open_positions(ticker, logger, s3_client)
    save_closed_positions_if_exist(s3_client, logger)


def process_executions_for_bracket_fills(executions: List[Dict], filled_tickers: Set[str],
                                         open_positions: Dict, logger: Logger, s3_client) -> None:
    """
    Process all executions to find bracket order fills.
    """
    for ticker in filled_tickers:
        position_data = open_positions.get(ticker)
        if not position_data:
            continue

        sell_execution = find_sell_execution_for_ticker(ticker, executions, filled_tickers)
        if not sell_execution:
            continue

        sell_data = extract_sell_execution_data(sell_execution)
        process_bracket_order_fill(ticker, position_data, sell_data, logger, s3_client)


def find_sell_execution_for_ticker(ticker: str, executions: List[Dict],
                                   filled_tickers: Set[str]) -> Optional[Dict]:
    """
    Find the most recent sell execution for a given ticker.
    """
    matching_sells = [
        exec_data for exec_data in executions
        if is_bracket_order_fill(ticker, exec_data, filled_tickers)
    ]

    if not matching_sells:
        return None

    return max(matching_sells, key=lambda x: x['time'])


def remove_ticker_from_open_positions(ticker: str, logger: Logger, s3_client) -> None:
    """
    Remove a ticker from open_positions.json after it's been closed.
    """
    from services.ibkr.ib_portfolio import (
        load_open_positions,
        save_and_upload_positions,
        open_positions_file_exists
    )

    if not open_positions_file_exists():
        return

    try:
        open_positions = load_open_positions()
        if ticker in open_positions:
            del open_positions[ticker]
            save_and_upload_positions(open_positions, s3_client, logger)
            logger.info(f"{ticker} removed from open_positions.json")
    except Exception as e:
        logger.error(f"Error removing {ticker} from open_positions.json: {e}")


def resolve_exit_type(sell_price: float, position_data: Dict) -> str:
    """
    Determine whether the exit was via Stop Loss or Take Profit based on prices.
    """
    stop_loss_price = position_data.get('stop_loss_price')
    take_profit_price = position_data.get('take_profit_price')

    if not isinstance(stop_loss_price, (int, float)):
        stop_loss_price = None
    if not isinstance(take_profit_price, (int, float)):
        take_profit_price = None

    if stop_loss_price and abs(sell_price - stop_loss_price) < 0.5:
        return 'STOP_LOSS'
    elif take_profit_price and abs(sell_price - take_profit_price) < 0.5:
        return 'TAKE_PROFIT'
    else:
        return 'BRACKET_ORDER'

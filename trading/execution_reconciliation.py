"""
Module to reconcile and create accurate closed positions from IBKR executions.
"""
from typing import Dict, List
from logging import Logger


def build_closed_position_from_executions(ticker: str, buy_execution: Dict, sell_execution: Dict) -> Dict:
    from datetime import datetime

    quantity = buy_execution['shares']
    buy_price = buy_execution['price']
    sell_price = sell_execution['price']

    profit = calculate_profit(sell_price, buy_price, quantity)
    return_pct = calculate_return_percentage(sell_price, buy_price)

    buy_time = datetime.fromisoformat(buy_execution['time'])
    sell_time = datetime.fromisoformat(sell_execution['time'])

    return {
        'symbol': ticker,
        'buy_date': buy_time.strftime('%Y-%m-%d'),
        'sell_date': sell_time.strftime('%Y-%m-%d'),
        'buy_price': round(buy_price, 2),
        'sell_price': round(sell_price, 2),
        'quantity': int(quantity),
        'profit': round(profit, 2),
        'return_pct': round(return_pct, 2),
        'buy_time': buy_time.strftime('%H:%M:%S'),
        'sell_time': sell_time.strftime('%H:%M:%S'),
        'buy_exec_id': buy_execution['exec_id'],
        'sell_exec_id': sell_execution['exec_id']
    }


def calculate_profit(sell_price: float, buy_price: float, quantity: float) -> float:
    return (sell_price - buy_price) * quantity


def calculate_return_percentage(sell_price: float, buy_price: float) -> float:
    if buy_price == 0:
        return 0.0
    return ((sell_price - buy_price) / buy_price) * 100


def extract_buy_executions(executions: List[Dict]) -> Dict[str, Dict]:
    buy_executions = {}
    for execution in executions:
        if is_buy_execution(execution):
            ticker = execution['ticker']
            if ticker not in buy_executions:
                buy_executions[ticker] = execution
            else:
                existing_time = execution_time(buy_executions[ticker])
                current_time = execution_time(execution)
                if current_time < existing_time:
                    buy_executions[ticker] = execution
    return buy_executions


def extract_sell_executions(executions: List[Dict]) -> Dict[str, Dict]:
    sell_executions = {}
    for execution in executions:
        if is_sell_execution(execution):
            ticker = execution['ticker']
            if ticker not in sell_executions:
                sell_executions[ticker] = execution
            else:
                existing_time = execution_time(sell_executions[ticker])
                current_time = execution_time(execution)
                if current_time > existing_time:
                    sell_executions[ticker] = execution
    return sell_executions


def execution_time(execution: Dict) -> str:
    return execution['time']


def find_matching_pairs(buy_executions: Dict[str, Dict], sell_executions: Dict[str, Dict]) -> List[tuple]:
    matching_pairs = []
    for ticker in buy_executions:
        if ticker in sell_executions:
            matching_pairs.append((ticker, buy_executions[ticker], sell_executions[ticker]))
    return matching_pairs


def generate_closed_positions_from_executions(executions: List[Dict], logger: Logger) -> List[Dict]:
    if not executions:
        logger.info("No executions found for today")
        return []

    buy_executions = extract_buy_executions(executions)
    sell_executions = extract_sell_executions(executions)

    logger.info(f"Found {len(buy_executions)} buy execution(s) and {len(sell_executions)} sell execution(s)")

    matching_pairs = find_matching_pairs(buy_executions, sell_executions)

    if not matching_pairs:
        logger.info("No matching buy-sell pairs found")
        return []

    closed_positions = []
    for ticker, buy_exec, sell_exec in matching_pairs:
        closed_position = build_closed_position_from_executions(ticker, buy_exec, sell_exec)
        closed_positions.append(closed_position)
        logger.info(
            f"{ticker} - Buy: ${closed_position['buy_price']:.2f} @ {closed_position['buy_time']}, "
            f"Sell: ${closed_position['sell_price']:.2f} @ {closed_position['sell_time']}, "
            f"P/L: ${closed_position['profit']:.2f} ({closed_position['return_pct']:.2f}%)"
        )

    logger.info(f"Generated {len(closed_positions)} accurate closed position(s) from IBKR executions")
    return closed_positions


def is_buy_execution(execution: Dict) -> bool:
    return execution['side'] in ['BOT', 'BUY']


def is_sell_execution(execution: Dict) -> bool:
    return execution['side'] in ['SLD', 'SELL']


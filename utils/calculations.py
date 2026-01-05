"""
Budget and price calculations for trading decisions.
"""
from typing import Dict
from json import loads


def load_settings() -> Dict:
    try:
        with open('files/settings.json', 'r') as f:
            return loads(f.read())
    except Exception:
        return {}


def get_next_investment_from_settings() -> float:
    settings = load_settings()
    return settings.get('nextInvestment', 0)


def get_ops_per_day_from_settings() -> int:
    settings = load_settings()
    return settings.get('opsPerDay', 1)


def get_stop_loss_percentage() -> float:
    settings = load_settings()
    return settings.get('stopLoss', 2.5)


def get_take_profit_percentage() -> float:
    settings = load_settings()
    return settings.get('takeProfit', 10)


def is_valid_budget_configuration(next_investment: float, ops_per_day: int) -> bool:
    return next_investment > 0 and ops_per_day > 0


def calculate_budget_per_trade() -> float:
    try:
        next_investment = get_next_investment_from_settings()
        ops_per_day = get_ops_per_day_from_settings()

        if is_valid_budget_configuration(next_investment, ops_per_day):
            return next_investment / ops_per_day

        return 0
    except Exception:
        return 0


def is_valid_price_and_budget(price: float, budget: float) -> bool:
    return budget > 0 and price > 0


def calculate_affordable_quantity(budget: float, price: float) -> int:
    return int(budget / price)


def can_afford_at_least_one_share(quantity: int) -> bool:
    return quantity >= 1


def calculate_quantity_from_budget(current_price: float) -> int:
    budget = calculate_budget_per_trade()

    if not is_valid_price_and_budget(current_price, budget):
        return 0

    quantity = calculate_affordable_quantity(budget, current_price)

    if not can_afford_at_least_one_share(quantity):
        return 0

    return quantity


def apply_stop_loss_percentage(price: float, percentage: float) -> float:
    return round(price * (1 - percentage / 100), 2)


def apply_take_profit_percentage(price: float, percentage: float) -> float:
    return round(price * (1 + percentage / 100), 2)


def calculate_stop_loss_price(buy_price: float) -> float:
    percentage = get_stop_loss_percentage()
    return apply_stop_loss_percentage(buy_price, percentage)


def calculate_take_profit_price(buy_price: float) -> float:
    percentage = get_take_profit_percentage()
    return apply_take_profit_percentage(buy_price, percentage)


def apply_threshold_multiplier(closing_price: float) -> float:
    from core.config import BUY_THRESHOLD_MULTIPLIER
    return round(closing_price * BUY_THRESHOLD_MULTIPLIER, 2)


def calculate_buy_threshold_price(closing_price: float) -> float:
    return apply_threshold_multiplier(closing_price)


def calculate_percentage_change(current: float, base: float) -> float:
    return round(((current - base) / base) * 100, 2)


def calculate_price_difference(current: float, base: float) -> float:
    return round(current - base, 2)


def calculate_price_change_percentage(current_price: float, closing_price: float) -> float:
    return ((current_price - closing_price) / closing_price) * 100

"""
State management for the trading application.
Stores in-memory state for positions and cached data.
"""
from typing import Dict, List, Optional

bought_shares_today: Dict[str, Dict[str, any]] = {}
closed_positions_today: List[Dict[str, any]] = []
daily_files_downloaded: bool = False
cached_settings: Optional[Dict] = None
cached_companies: Optional[List[str]] = None
in_closing_phase: bool = False
allow_order_placement: bool = True


def reset_daily_state() -> None:
    global bought_shares_today, closed_positions_today, daily_files_downloaded
    bought_shares_today.clear()
    closed_positions_today.clear()
    daily_files_downloaded = False


def mark_files_as_downloaded() -> None:
    global daily_files_downloaded
    daily_files_downloaded = True


def is_files_downloaded() -> bool:
    return daily_files_downloaded


def get_bought_shares() -> Dict[str, Dict[str, any]]:
    return bought_shares_today


def get_closed_positions() -> List[Dict[str, any]]:
    return closed_positions_today


def add_bought_share(ticker: str, share_data: Dict) -> None:
    bought_shares_today[ticker] = share_data


def remove_bought_share(ticker: str) -> None:
    bought_shares_today.pop(ticker, None)


def add_closed_position(position_data: Dict) -> None:
    closed_positions_today.append(position_data)


def is_ticker_bought(ticker: str) -> bool:
    return ticker in bought_shares_today


def get_share_data(ticker: str) -> Optional[Dict]:
    return bought_shares_today.get(ticker)


def set_closing_phase() -> None:
    global in_closing_phase, allow_order_placement
    in_closing_phase = True
    allow_order_placement = False


def is_in_closing_phase() -> bool:
    return in_closing_phase


def disable_order_placement() -> None:
    global allow_order_placement
    allow_order_placement = False


def is_order_placement_allowed() -> bool:
    return allow_order_placement

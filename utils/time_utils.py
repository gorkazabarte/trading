"""
Date and time utility functions.
"""
from datetime import datetime, timezone, timedelta, time
from core.config import MARKET_CLOSE_TIME


def create_market_close_datetime() -> datetime:
    return datetime.combine(datetime.today(), MARKET_CLOSE_TIME)


def create_current_datetime(current_time: time) -> datetime:
    return datetime.combine(datetime.today(), current_time)


def calculate_time_difference_in_seconds(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds()


def convert_seconds_to_minutes(seconds: float) -> int:
    return int(seconds / 60)


def calculate_minutes_until_close(current_time: time) -> int:
    close_datetime = create_market_close_datetime()
    current_datetime = create_current_datetime(current_time)
    seconds = calculate_time_difference_in_seconds(current_datetime, close_datetime)
    return convert_seconds_to_minutes(seconds)


def get_current_eastern_time() -> time:
    eastern_offset = timedelta(hours=-5)
    eastern_time = datetime.now(timezone.utc) + eastern_offset
    return eastern_time.time()


def get_current_date() -> tuple[int, int, int]:
    now = datetime.now(timezone.utc)
    return now.year, now.month, now.day


def get_current_date_string() -> str:
    year, month, day = get_current_date()
    return f"{year}-{month:02d}-{day:02d}"


def is_market_hours_now() -> bool:
    from core.config import MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE, MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE
    current_time = get_current_eastern_time()
    market_open = time(MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE)
    market_close = time(MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE)
    return market_open <= current_time <= market_close


def is_close_to_market_close() -> bool:
    from core.config import MINUTES_BEFORE_CLOSE_TO_SELL
    current_time = get_current_eastern_time()
    minutes_until_close = calculate_minutes_until_close(current_time)
    return 0 <= minutes_until_close <= MINUTES_BEFORE_CLOSE_TO_SELL


def should_exit_at_market_close() -> bool:
    current_time = get_current_eastern_time()
    return current_time > MARKET_CLOSE_TIME

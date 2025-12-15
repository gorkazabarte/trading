from datetime import datetime, time

CLOSING_PRICE_PREFIX = 'C'
DELAYED_PAST_CLOSE_CODE = 'DPB'
MARKET_CLOSE_TIME = time(16, 0)
MARKET_OPEN_TIME = time(9, 30)
OPENING_PRICE_PREFIX = 'O'


def get_current_eastern_time() -> time:
    from datetime import timedelta, timezone
    eastern_offset = timedelta(hours=-5)
    eastern_time = datetime.now(timezone.utc) + eastern_offset
    return eastern_time.time()


def is_during_market_hours() -> bool:
    current_time = get_current_eastern_time()
    return MARKET_OPEN_TIME <= current_time <= MARKET_CLOSE_TIME


def create_empty_result(market_data: dict) -> dict:
    return {
        'conid': market_data.get('conid'),
        'last_price': None,
        'previous_close': None,
        'change_from_close': None,
        'change_from_close_percent': None,
        'bid_price': None,
        'ask_price': None,
        'volume': None,
        'volume_raw': None,
        'is_market_closed': False,
        'price_type': None,
        'exchange_code': None,
        'timestamp': None
    }


def is_delayed_past_close(exchange_code: str) -> bool:
    return exchange_code == DELAYED_PAST_CLOSE_CODE


def has_closing_price_prefix(price_str: str) -> bool:
    return isinstance(price_str, str) and price_str.startswith(CLOSING_PRICE_PREFIX)


def has_opening_price_prefix(price_str: str) -> bool:
    return isinstance(price_str, str) and price_str.startswith(OPENING_PRICE_PREFIX)


def parse_price_with_prefix(price_str, result: dict) -> None:
    if has_closing_price_prefix(price_str):
        result['price_type'] = 'Closing Price'
        result['is_market_closed'] = True
        result['last_price'] = price_str[1:]
    elif has_opening_price_prefix(price_str):
        result['price_type'] = 'Opening Price'
        result['last_price'] = price_str[1:]
    else:
        result['price_type'] = 'Last Trade'
        result['last_price'] = price_str


def parse_last_price(market_data: dict, result: dict) -> None:
    price_str = market_data.get('31')
    if not price_str:
        return

    if isinstance(price_str, str):
        parse_price_with_prefix(price_str, result)
    else:
        result['last_price'] = str(price_str)


def calculate_previous_close(change_value: float, current_price: float) -> str:
    return str(round(current_price - change_value, 2))


def parse_change_from_close(market_data: dict, result: dict) -> None:
    change_str = market_data.get('82')
    if not change_str or not result['last_price']:
        return

    try:
        change_value = float(str(change_str).replace('+', ''))
        result['change_from_close'] = change_value

        current_price = float(result['last_price'])
        result['previous_close'] = calculate_previous_close(change_value, current_price)
    except (ValueError, TypeError):
        pass


def parse_change_percentage(market_data: dict, result: dict) -> None:
    change_pct_str = market_data.get('83')
    if not change_pct_str:
        return

    try:
        result['change_from_close_percent'] = float(str(change_pct_str))
    except (ValueError, TypeError):
        pass


def parse_timestamp(market_data: dict, result: dict) -> None:
    timestamp_ms = market_data.get('_updated')
    if timestamp_ms:
        result['timestamp'] = datetime.fromtimestamp(timestamp_ms / 1000)


def calculate_spread(bid: float, ask: float) -> tuple:
    spread = round(ask - bid, 2)
    spread_percent = round((ask - bid) / bid * 100, 2) if bid > 0 else None
    return spread, spread_percent


def parse_spread(result: dict) -> None:
    if not result['bid_price'] or not result['ask_price']:
        return

    try:
        bid = float(result['bid_price'])
        ask = float(result['ask_price'])
        result['spread'], result['spread_percent'] = calculate_spread(bid, ask)
    except (ValueError, TypeError):
        result['spread'] = None
        result['spread_percent'] = None


def parse_market_data(market_data: dict) -> dict:
    result = create_empty_result(market_data)

    exchange_code = market_data.get('6509')
    result['exchange_code'] = exchange_code

    if is_delayed_past_close(exchange_code):
        result['is_market_closed'] = True

    parse_last_price(market_data, result)
    parse_change_from_close(market_data, result)
    parse_change_percentage(market_data, result)

    result['bid_price'] = market_data.get('84')
    result['ask_price'] = market_data.get('86')
    result['volume'] = market_data.get('87')
    result['volume_raw'] = market_data.get('87_raw')

    parse_timestamp(market_data, result)
    parse_spread(result)

    if is_during_market_hours() and result['price_type'] == 'Last Trade':
        result['is_market_closed'] = False

    return result


def format_price_info(parsed_data: dict) -> str:
    if not parsed_data['last_price']:
        return "N/A"

    price_info = f"${parsed_data['last_price']}"
    if parsed_data['price_type']:
        price_info += f" ({parsed_data['price_type']})"

    return price_info


def format_spread_info(parsed_data: dict) -> str:
    if parsed_data.get('spread') is None:
        return ""

    return f" | Spread: ${parsed_data['spread']} ({parsed_data['spread_percent']}%)"


def format_volume_info(parsed_data: dict) -> str:
    if not parsed_data['volume']:
        return ""

    return f" | Vol: {parsed_data['volume']}"


def format_market_data_log(ticker: str, parsed_data: dict) -> str:
    status = "CLOSED" if parsed_data['is_market_closed'] else "OPEN"

    price_info = format_price_info(parsed_data)
    bid_info = f"${parsed_data['bid_price']}" if parsed_data['bid_price'] else "N/A"
    ask_info = f"${parsed_data['ask_price']}" if parsed_data['ask_price'] else "N/A"
    spread_info = format_spread_info(parsed_data)
    vol_info = format_volume_info(parsed_data)

    return f"{ticker} {status} - Price: {price_info}, Bid: {bid_info}, Ask: {ask_info}{spread_info}{vol_info}"

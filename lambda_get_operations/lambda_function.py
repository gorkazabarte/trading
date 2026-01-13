from json import dumps, loads
from os import environ
from datetime import datetime, timedelta

from boto3 import client


CLOSED_POSITIONS_FILENAME = 'closed_positions.json'
CONTENT_TYPE_JSON = 'application/json'
CORS_ALLOW_ALL_ORIGINS = '*'
CORS_HEADERS = 'Content-Type'
CORS_METHODS = 'GET,POST,OPTIONS'
DATE_FORMAT_TWO_DIGITS = '02d'
DEFAULT_DAYS_LOOKBACK = 5
DEFAULT_S3_BUCKET = 'dev-trading-data-storage'
DECIMAL_PLACES = 2
EMPTY_BODY = '{}'
HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_ERROR = 500
HTTP_OK = 200
MAX_DAYS_ALLOWED = 365
MIN_DAYS_ALLOWED = 1
PERCENTAGE_MULTIPLIER = 100
PROFIT_KEY = 'profit'
UTF8_ENCODING = 'utf-8'

s3_client = client('s3')
S3_BUCKET = environ.get('S3_BUCKET', DEFAULT_S3_BUCKET)


def build_cors_headers():
    return {
        'Content-Type': CONTENT_TYPE_JSON,
        'Access-Control-Allow-Origin': CORS_ALLOW_ALL_ORIGINS,
        'Access-Control-Allow-Headers': CORS_HEADERS,
        'Access-Control-Allow-Methods': CORS_METHODS
    }


def build_date_tuple(date):
    return date.year, date.month, date.day


def build_empty_statistics():
    return {
        'total_trades': 0,
        'winning_trades': 0,
        'losing_trades': 0,
        'total_profit': 0.0,
        'avg_profit_per_trade': 0.0,
        'win_rate': 0.0
    }


def build_error_response(status_code, error_message):
    return {
        'statusCode': status_code,
        'headers': {CONTENT_TYPE_JSON: CONTENT_TYPE_JSON},
        'body': dumps({'error': error_message})
    }


def build_s3_key_for_closed_positions(year, month, day):
    return f"{year}/{month:{DATE_FORMAT_TWO_DIGITS}}/{day:{DATE_FORMAT_TWO_DIGITS}}/{CLOSED_POSITIONS_FILENAME}"


def build_statistics_from_positions(positions):
    total_trades = count_total_trades(positions)
    winning_trades = count_winning_trades(positions)
    losing_trades = count_losing_trades(positions)
    total_profit = calculate_total_profit(positions)

    return {
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'total_profit': round_to_decimal_places(total_profit),
        'avg_profit_per_trade': calculate_average_profit(total_profit, total_trades),
        'win_rate': calculate_win_rate(winning_trades, total_trades)
    }


def build_success_response(response_data):
    return {
        'statusCode': HTTP_OK,
        'headers': build_cors_headers(),
        'body': dumps(response_data)
    }


def calculate_average_profit(total_profit, total_trades):
    if total_trades == 0:
        return 0.0
    average = total_profit / total_trades
    return round_to_decimal_places(average)


def calculate_statistics(positions):
    if has_no_positions(positions):
        return build_empty_statistics()
    return build_statistics_from_positions(positions)


def calculate_total_profit(positions):
    return sum(extract_profit_from_position(position) for position in positions)


def calculate_win_rate(winning_trades, total_trades):
    if total_trades == 0:
        return 0.0
    win_rate = (winning_trades / total_trades) * PERCENTAGE_MULTIPLIER
    return round_to_decimal_places(win_rate)


def collect_all_positions_for_date_range(date_range):
    all_positions = []
    for year, month, day in date_range:
        positions = load_closed_positions_for_date(year, month, day)
        all_positions.extend(positions)
    return all_positions


def count_losing_trades(positions):
    return sum(1 for position in positions if is_losing_trade(position))


def count_total_trades(positions):
    return len(positions)


def count_winning_trades(positions):
    return sum(1 for position in positions if is_winning_trade(position))


def create_response_data(days_back, statistics, positions):
    return {
        'period': f'Last {days_back} days',
        'statistics': statistics,
        'positions': positions
    }


def decode_s3_object_body(s3_object):
    return s3_object['Body'].read().decode(UTF8_ENCODING)


def extract_days_from_event(event):
    days = try_extract_days_from_query_parameters(event)
    if days is not None:
        return days
    return extract_days_from_request_body(event)


def extract_days_from_query_parameters(query_params):
    try:
        return int(query_params['days'])
    except (ValueError, TypeError, KeyError):
        return None


def extract_days_from_request_body(event):
    body = parse_request_body(event)
    return body.get('days', DEFAULT_DAYS_LOOKBACK)


def extract_profit_from_position(position):
    return position.get(PROFIT_KEY, 0)


def generate_date_range(days_back):
    end_date = get_current_date()
    start_date = get_start_date(end_date, days_back)
    return generate_dates_between(start_date, end_date)


def generate_dates_between(start_date, end_date):
    date_list = []
    current_date = start_date

    while is_before_or_equal(current_date, end_date):
        date_list.append(build_date_tuple(current_date))
        current_date = get_next_day(current_date)

    return date_list


def get_current_date():
    return datetime.now()


def get_next_day(date):
    return date + timedelta(days=1)


def get_query_parameters_from_event(event):
    return event.get('queryStringParameters')


def get_start_date(end_date, days_back):
    return end_date - timedelta(days=days_back)


def has_days_parameter(query_params):
    return query_params is not None and 'days' in query_params


def has_no_positions(positions):
    return not positions


def is_before_or_equal(date1, date2):
    return date1 <= date2


def is_days_within_valid_range(days):
    return isinstance(days, int) and MIN_DAYS_ALLOWED <= days <= MAX_DAYS_ALLOWED


def is_list(data):
    return isinstance(data, list)


def is_losing_trade(position):
    return extract_profit_from_position(position) < 0


def is_winning_trade(position):
    return extract_profit_from_position(position) > 0


def lambda_handler(event, context):
    try:
        days_back = extract_days_from_event(event)

        if not is_days_within_valid_range(days_back):
            return build_error_response(
                HTTP_BAD_REQUEST,
                'days must be an integer between 1 and 365'
            )

        date_range = generate_date_range(days_back)
        all_positions = collect_all_positions_for_date_range(date_range)
        statistics = calculate_statistics(all_positions)
        response_data = create_response_data(days_back, statistics, all_positions)

        return build_success_response(response_data)

    except Exception as e:
        return build_error_response(
            HTTP_INTERNAL_ERROR,
            f'Failed to retrieve closed positions: {str(e)}'
        )


def load_closed_positions_for_date(year, month, day):
    s3_key = build_s3_key_for_closed_positions(year, month, day)
    return try_load_from_s3(s3_key)


def parse_json_string(json_string):
    return loads(json_string)


def parse_request_body(event):
    body = event.get('body', EMPTY_BODY)
    if isinstance(body, str):
        return parse_json_string(body)
    return body


def retrieve_s3_object(s3_key):
    return s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)


def round_to_decimal_places(value):
    return round(value, DECIMAL_PLACES)


def try_extract_days_from_query_parameters(event):
    query_params = get_query_parameters_from_event(event)
    if has_days_parameter(query_params):
        return extract_days_from_query_parameters(query_params)
    return None


def try_load_from_s3(s3_key):
    try:
        s3_object = retrieve_s3_object(s3_key)
        json_data = decode_s3_object_body(s3_object)
        data = parse_json_string(json_data)
        return data if is_list(data) else []
    except s3_client.exceptions.NoSuchKey:
        return []
    except Exception:
        return []


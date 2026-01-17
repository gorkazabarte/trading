from datetime import date, datetime, timedelta
from io import StringIO
from json import dumps
from os import environ

from boto3 import client
from pandas import read_csv
from yfinance import Ticker

MAX_SHARE_PRICE = float(environ.get("MAX_SHARE_PRICE", "500.0"))
MIN_SHARE_PRICE = float(environ.get("MIN_SHARE_PRICE", "5.0"))
PERCENTAGE_CHANGE_90D = float(environ.get("PERCENTAGE_CHANGE_90D", "10.0"))
S3_BUCKET = environ.get("S3_BUCKET")

s3 = client("s3")


def build_csv_key_for_date(year: int, month: int, day: int) -> str:
    return f"{year}/{month:02}/{day:02}/all_companies.csv"


def build_filtered_json_key(year: int, month: int, day: int) -> str:
    return f"{year}/{month:02}/{day:02}/filtered_companies.json"


def build_response(companies: dict, year: int, month: int, day: int) -> dict:
    return {
        "statusCode": 200,
        "body": {
            "message": "Success",
            "records_uploaded": len(companies),
            "s3_bucket": S3_BUCKET,
            "s3_key": build_filtered_json_key(year, month, day)
        }
    }


def calculate_ninety_day_range() -> tuple[datetime, datetime]:
    end_date = datetime.today()
    start_date = end_date - timedelta(days=90)
    return start_date, end_date


def calculate_percentage_change(start_price: float, end_price: float) -> float:
    return ((end_price - start_price) / start_price) * 100


def count_separators_in_first_line(csv_content: str) -> tuple[int, int]:
    first_line = csv_content.split('\n')[0]
    semicolon_count = first_line.count(';')
    comma_count = first_line.count(',')
    return semicolon_count, comma_count


def create_company_dictionary(symbol: str, symbol_data, performance: dict) -> dict:
    return {
        "symbol": symbol,
        "company": extract_column_value(symbol_data, ["Company", "company"]),
        "event_name": extract_column_value(symbol_data, ["Event Name", "event_name", "Event"]),
        "earnings_call_time": extract_column_value(symbol_data, ["Earnings Call Time", "earnings_call_time", "Time"]),
        "current_price": round(performance["current_price"], 4),
        "percentage_change_90d": round(performance["percent_change_90d"], 4),
        "market_cap": extract_column_value(symbol_data, ["Market Cap", "market_cap", "MarketCap"]),
        "trailing_pe": performance.get("trailing_pe"),
        "forward_pe": performance.get("forward_pe")
    }


def detect_csv_separator(csv_content: str) -> str:
    semicolon_count, comma_count = count_separators_in_first_line(csv_content)
    return ';' if semicolon_count > comma_count else ','


def download_csv_content(year: int, month: int, day: int) -> str:
    key = build_csv_key_for_date(year, month, day)
    s3_object = s3.get_object(Bucket=S3_BUCKET, Key=key)
    return s3_object["Body"].read().decode("utf-8")


def extract_column_value(data, possible_column_names: list) -> str:
    for column_name in possible_column_names:
        if column_name in data:
            return data.get(column_name, "")
    return ""


def extract_current_price_from_history(stock: Ticker) -> float:
    return stock.history(period="1d")["Close"].iloc[-1]


def extract_date_from_event(event: dict) -> tuple[int, int, int]:
    key = event.get("key")
    year, month, day, _ = key.split("/")

    if year and month and day:
        return int(year), int(month), int(day)

    return get_todays_date()


def extract_forward_pe_ratio(stock_info: dict) -> float:
    forward_pe_raw = stock_info.get("forwardPE")
    if forward_pe_raw:
        return round(float(forward_pe_raw), 2)
    return None


def extract_price_extremes(historical_data) -> tuple[float, float]:
    high_ninety_days = historical_data["High"].max()
    low_ninety_days = historical_data["Low"].min()
    return float(high_ninety_days), float(low_ninety_days)


def extract_price_range_from_history(historical_data) -> tuple[float, float, float]:
    start_price = historical_data["Close"].iloc[0]
    end_price = historical_data["Close"].iloc[-1]
    percentage_change = calculate_percentage_change(start_price, end_price)
    return float(start_price), float(end_price), float(percentage_change)


def extract_stock_info_safely(stock: Ticker) -> dict:
    try:
        return stock.info
    except Exception:
        return {}


def extract_trailing_pe_ratio(stock_info: dict) -> float:
    trailing_pe_raw = stock_info.get("trailingPE")
    if trailing_pe_raw:
        return round(float(trailing_pe_raw), 2)
    return None


def extract_unique_symbols_from_dataframe(dataframe) -> list:
    return dataframe["Symbol"].dropna().unique().tolist()


def fetch_historical_stock_data(stock: Ticker, start_date: datetime, end_date: datetime):
    return stock.history(start=start_date, end=end_date)


def fetch_pe_ratios(stock: Ticker) -> tuple[float, float]:
    stock_info = extract_stock_info_safely(stock)
    trailing_pe = extract_trailing_pe_ratio(stock_info)
    forward_pe = extract_forward_pe_ratio(stock_info)
    return trailing_pe, forward_pe


def fetch_stock_performance_data(ticker: str) -> dict:
    start_date, end_date = calculate_ninety_day_range()

    stock = Ticker(ticker)
    current_price = extract_current_price_from_history(stock)
    historical_data = fetch_historical_stock_data(stock, start_date, end_date)

    start_price, end_price, percentage_change = extract_price_range_from_history(historical_data)
    high_ninety_days, low_ninety_days = extract_price_extremes(historical_data)
    trailing_pe, forward_pe = fetch_pe_ratios(stock)

    return {
        "ticker": ticker,
        "current_price": float(current_price),
        "start_price_90d": start_price,
        "end_price_90d": end_price,
        "percent_change_90d": percentage_change,
        "90d_high": high_ninety_days,
        "90d_low": low_ninety_days,
        "trailing_pe": trailing_pe,
        "forward_pe": forward_pe
    }


def filter_companies_with_after_market_earnings(dataframe):
    validate_earnings_call_time_column_exists(dataframe)
    return dataframe[dataframe["Earnings Call Time"] == "AMC"].copy()


def get_todays_date() -> tuple[int, int, int]:
    today = date.today()
    return today.year, today.month, today.day


def is_price_above_minimum(current_price: float) -> bool:
    return current_price > MIN_SHARE_PRICE


def is_price_below_maximum(current_price: float) -> bool:
    return current_price < MAX_SHARE_PRICE


def is_price_in_valid_range(current_price: float) -> bool:
    return is_price_above_minimum(current_price) and is_price_below_maximum(current_price)


def is_percentage_change_sufficient(percentage_change: float) -> bool:
    return percentage_change > PERCENTAGE_CHANGE_90D


def lambda_handler(event, context):
    year, month, day = extract_date_from_event(event)

    csv_content = download_csv_content(year, month, day)
    dataframe = parse_csv_content(csv_content)
    filtered_dataframe = filter_companies_with_after_market_earnings(dataframe)

    symbols = extract_unique_symbols_from_dataframe(filtered_dataframe)
    qualified_companies = process_all_symbols(symbols, filtered_dataframe)

    upload_filtered_companies_to_s3(qualified_companies, year, month, day)

    return build_response(qualified_companies, year, month, day)


def parse_csv_content(csv_content: str):
    separator = detect_csv_separator(csv_content)
    return read_csv(StringIO(csv_content), sep=separator)


def process_all_symbols(symbols: list, filtered_dataframe) -> dict:
    qualified_companies = {}

    for symbol in symbols:
        company_data = try_process_single_symbol(symbol, filtered_dataframe)
        if company_data:
            qualified_companies[symbol] = company_data

    return qualified_companies


def qualifies_for_trading(current_price: float, percentage_change: float) -> bool:
    return is_price_in_valid_range(current_price) and is_percentage_change_sufficient(percentage_change)


def retrieve_symbol_data_from_dataframe(symbol: str, dataframe):
    return dataframe[dataframe["Symbol"] == symbol].iloc[0]


def try_process_single_symbol(symbol: str, filtered_dataframe):
    try:
        performance_data = fetch_stock_performance_data(symbol)
        current_price = performance_data["current_price"]
        percentage_change = performance_data["percent_change_90d"]

        if qualifies_for_trading(current_price, percentage_change):
            symbol_data = retrieve_symbol_data_from_dataframe(symbol, filtered_dataframe)
            return create_company_dictionary(symbol, symbol_data, performance_data)
    except Exception:
        pass

    return None


def upload_filtered_companies_to_s3(companies: dict, year: int, month: int, day: int) -> None:
    key = build_filtered_json_key(year, month, day)
    json_content = dumps(companies)

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json_content,
        ContentType="application/json"
    )


def validate_earnings_call_time_column_exists(dataframe):
    if "Earnings Call Time" not in dataframe.columns:
        available_columns = ', '.join(dataframe.columns.tolist())
        raise ValueError(f"Column 'Earnings Call Time' not found. Available columns: {available_columns}")

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


def build_company_data(symbol: str, symbol_data, performance: dict) -> dict:

    def get_column_value(data, possible_names):
        for name in possible_names:
            if name in data:
                return data.get(name, "")
        return ""

    return {
        "symbol": symbol,
        "company": get_column_value(symbol_data, ["Company", "company"]),
        "event_name": get_column_value(symbol_data, ["Event Name", "event_name", "Event"]),
        "earnings_call_time": get_column_value(symbol_data, ["Earnings Call Time", "earnings_call_time", "Time"]),
        "current_price": round(performance["current_price"], 4),
        "percentage_change_90d": round(performance["percent_change_90d"], 4),
        "market_cap": get_column_value(symbol_data, ["Market Cap", "market_cap", "MarketCap"])
    }


def build_s3_key(year: int, month: int, day: int) -> str:
    return f"{year}/{month:02}/{day:02}/filtered_companies.json"


def calculate_date_range() -> tuple[datetime, datetime]:
    end = datetime.today()
    start = end - timedelta(days=90)
    return start, end


def download_csv_from_s3(year: int, month: int, day: int) -> str:
    key = f"{year}/{month:02}/{day:02}/all_companies.csv"
    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    return obj["Body"].read().decode("utf-8")


def extract_unique_symbols(df) -> list:
    return df["Symbol"].dropna().unique().tolist()


def filter_after_market_close(df):
    if "Earnings Call Time" not in df.columns:
        available_cols = ', '.join(df.columns.tolist())
        raise ValueError(f"Column 'Earnings Call Time' not found. Available columns: {available_cols}")

    return df[df["Earnings Call Time"] == "AMC"].copy()


def get_stock_performance(ticker: str) -> dict:
    start, end = calculate_date_range()

    stock = Ticker(ticker)
    current_price = stock.history(period="1d")["Close"].iloc[-1]

    df = stock.history(start=start, end=end)

    start_price = df["Close"].iloc[0]
    end_price = df["Close"].iloc[-1]
    pct_change = ((end_price - start_price) / start_price) * 100

    high_90 = df["High"].max()
    low_90 = df["Low"].min()

    return {
        "ticker": ticker,
        "current_price": float(current_price),
        "start_price_90d": float(start_price),
        "end_price_90d": float(end_price),
        "percent_change_90d": float(pct_change),
        "90d_high": float(high_90),
        "90d_low": float(low_90),
    }


def get_target_day(event: dict) -> tuple[int, int, int]:

    print("Event received:", event)
    body = event.get("body", {})
    print("Body extracted:", body)

    if isinstance(body, str):
        from json import loads
        body = loads(body)

    year = body.get("year")
    month = body.get("month")
    day = body.get("day")

    if year and month and day:
        return int(year), int(month), int(day)

    today = date.today()

    return today.year, today.month, today.day


def is_within_price_range(current_price: float) -> bool:
    return MIN_SHARE_PRICE < current_price < MAX_SHARE_PRICE


def lambda_handler(event, context):
    year, month, day = get_target_day(event)

    csv_data = download_csv_from_s3(year, month, day)
    df = read_csv(StringIO(csv_data), sep=';')
    df_filtered = filter_after_market_close(df)

    symbols = extract_unique_symbols(df_filtered)
    companies = process_symbols(symbols, df_filtered)

    save_to_s3(companies, year, month, day)

    return {
        "statusCode": 200,
        "body": {
            "message": "Success",
            "records_uploaded": len(companies),
            "s3_bucket": S3_BUCKET,
            "s3_key": build_s3_key(year, month, day)
        }
    }


def meets_percentage_threshold(percentage_change: float) -> bool:
    return percentage_change > PERCENTAGE_CHANGE_90D


def process_symbols(symbols: list, df_filtered) -> dict:
    companies = {}

    for symbol in symbols:
        try:
            performance = get_stock_performance(symbol)
            current_price = performance["current_price"]
            percentage_change_90d = performance["percent_change_90d"]

            if should_include_symbol(current_price, percentage_change_90d):
                symbol_data = df_filtered[df_filtered["Symbol"] == symbol].iloc[0]
                companies[symbol] = build_company_data(symbol, symbol_data, performance)
        except Exception:
            continue

    return companies


def save_to_s3(companies: dict, year: int, month: int, day: int) -> None:
    key = build_s3_key(year, month, day)
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=dumps(companies),
        ContentType="application/json"
    )


def should_include_symbol(current_price: float, percentage_change: float) -> bool:
    return is_within_price_range(current_price) and meets_percentage_threshold(percentage_change)

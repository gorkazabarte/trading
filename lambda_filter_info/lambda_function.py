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
    return {
        "current_price": round(performance["current_price"], 4),
        "date": str(symbol_data["Date"]),
        "time": symbol_data["Time"],
        "percentage_change_90d": round(performance["percent_change_90d"], 4)
    }


def build_s3_key(year: int, month: int) -> str:
    return f"{year}/{month:02}/filtered_companies.json"


def calculate_date_range() -> tuple[datetime, datetime]:
    end = datetime.today()
    start = end - timedelta(days=90)
    return start, end


def download_csv_from_s3(year: int, month: int) -> str:
    key = f"{year}/{month:02}/all_companies.csv"
    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    return obj["Body"].read().decode("utf-8")


def extract_unique_symbols(df) -> list:
    return df["Symbol"].dropna().unique().tolist()


def filter_before_market_open(df):
    return df[df["Time"] != "before-market-open"].copy()


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


def get_target_month() -> tuple[int, int]:
    today = date.today()

    env_year = environ.get("YEAR")
    env_month = environ.get("MONTH")

    if env_year and env_month:
        return int(env_year), int(env_month)

    return today.year, today.month


def is_within_price_range(current_price: float) -> bool:
    return MIN_SHARE_PRICE < current_price < MAX_SHARE_PRICE


def lambda_handler(event, context):
    year, month = get_target_month()

    csv_data = download_csv_from_s3(year, month)
    df = read_csv(StringIO(csv_data))
    df_filtered = filter_before_market_open(df)

    symbols = extract_unique_symbols(df_filtered)
    companies = process_symbols(symbols, df_filtered)

    save_to_s3(companies, year, month)

    return {
        "statusCode": 200,
        "body": {
            "message": "Success",
            "records_uploaded": len(companies),
            "s3_bucket": S3_BUCKET,
            "s3_key": build_s3_key(year, month)
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


def save_to_s3(companies: dict, year: int, month: int) -> None:
    key = build_s3_key(year, month)
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=dumps(companies),
        ContentType="application/json"
    )


def should_include_symbol(current_price: float, percentage_change: float) -> bool:
    return is_within_price_range(current_price) and meets_percentage_threshold(percentage_change)


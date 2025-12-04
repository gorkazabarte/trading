from datetime import date, datetime, timedelta
from io import StringIO
from json import dumps
from os import environ

from boto3 import client
from pandas import read_csv
from yfinance import Ticker

S3_BUCKET = environ.get("S3_BUCKET")

MAX_SHARE_PRICE = float(environ.get("MAX_SHARE_PRICE", "500.0"))
MIN_SHARE_PRICE = float(environ.get("MIN_SHARE_PRICE", "5.0"))
PERCENTAGE_CHANGE_90D = float(environ.get("PERCENTAGE_CHANGE_90D", "10.0"))

s3 = client("s3")

def get_target_month():
    """Return the year/month to process, based on env vars or next month."""
    today = date.today()

    env_year = environ.get("YEAR")
    env_month = environ.get("MONTH")

    if env_year and env_month:
        return int(env_year), int(env_month)

    return today.year, today.month

def get_stock_performance(ticker: str):

    end = datetime.today()
    start = end - timedelta(days=90)

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

def save_to_s3(companies, year, month):

    key = f"{year}/{month:02}/filtered_companies.json"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=dumps(companies),
        ContentType="application/json"
    )



def lambda_handler(event, context):

    year, month = get_target_month()

    key = f"{year}/{month:02}/all_companies.csv"

    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    data = obj["Body"].read().decode("utf-8")

    df = read_csv(StringIO(data))
    symbols = df["Symbol"].dropna().unique().tolist()
    companies = {}

    for symbol in symbols[:]:
        try:
            performance = get_stock_performance(symbol)
            current_price = performance["current_price"]
            percentage_change_90d = performance["percent_change_90d"]

            if MIN_SHARE_PRICE < current_price < MAX_SHARE_PRICE and percentage_change_90d > PERCENTAGE_CHANGE_90D:
                symbol_date = df[df["Symbol"] == symbol]["Date"].iloc[0]

                companies[symbol] = {
                    "current_price": round(current_price, 4),
                    "date": str(symbol_date),
                    "percentage_change_90d": round(percentage_change_90d, 4)
                }
        except Exception as e:
            symbols.remove(symbol)

    save_to_s3(companies, year, month)

    return {
            "statusCode": 200,
            "body": {
                "message": "Success",
                "records_uploaded": len(companies),
                "s3_bucket": S3_BUCKET,
                "s3_key": f"{year}/{month:02}/filtered_companies.json"
            }
        }

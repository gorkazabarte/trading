from calendar import monthrange
from datetime import date
from os import environ

from boto3 import client
from pandas import DataFrame
from requests import get

FINNHUB_API_TOKEN = environ.get("FINNHUB_API_TOKEN", "d4bgvrhr01qnomk4rodgd4bgvrhr01qnomk4roe0")
HEADERS = {"User-Agent": "Mozilla/5.0"}
ROWS_PER_PAGE = 1000
S3_BUCKET = environ.get("S3_BUCKET")

s3 = client("s3")


def build_finnhub_earnings_record(item: dict, symbol: str, earnings_date: str) -> dict:
    hour = item.get("hour", "")
    time_mapping = {
        "bmo": "before-market-open",
        "amc": "after-market-close",
        "": "time-not-supplied"
    }
    time_display = time_mapping.get(hour, hour)

    return {
        "Company": symbol,
        "Date": earnings_date,
        "EPS Estimate": item.get("epsEstimate"),
        "Market Cap": None,
        "Symbol": symbol,
        "Time": time_display,
        "Source": "Finnhub"
    }


def build_nasdaq_earnings_record(item: dict, current_date: date) -> dict:
    return {
        "Company": item.get("name"),
        "Date": current_date.isoformat(),
        "EPS Estimate": item.get("epsForecast"),
        "Market Cap": item.get("marketCap"),
        "Symbol": item.get("symbol"),
        "Time": item.get("time"),
        "Source": "Nasdaq"
    }


def build_s3_key(year: int, month: int) -> str:
    return f"{year}/{month:02}/all_companies.csv"


def calculate_source_counts(records: list) -> tuple[int, int]:
    nasdaq_count = sum(1 for r in records if r.get("Source") == "Nasdaq")
    finnhub_count = sum(1 for r in records if r.get("Source") == "Finnhub")
    return nasdaq_count, finnhub_count


def convert_to_dataframe(records: list) -> DataFrame:
    df = DataFrame(records)

    if not df.empty:
        df = df.sort_values(by=["Date", "Symbol"]).reset_index(drop=True)

    return df


def fetch_earnings_for_day(year: int, month: int, day: int) -> list:
    all_rows = []
    offset = 0

    while True:
        url = "https://api.nasdaq.com/api/calendar/earnings"
        params = {
            "date": f"{year}-{month:02}-{day:02}",
            "type": "earning",
            "limit": ROWS_PER_PAGE,
            "offset": offset
        }

        resp = get(url, headers=HEADERS, params=params)
        resp.raise_for_status()

        data = resp.json()
        rows = data.get("data", {}).get("rows", [])

        if not rows:
            break

        all_rows.extend(rows)

        if has_more_pages(rows):
            offset += ROWS_PER_PAGE
        else:
            break

    return all_rows


def fetch_finnhub_earnings(from_date: str, to_date: str) -> list:
    url = "https://finnhub.io/api/v1/calendar/earnings"
    params = {
        "from": from_date,
        "to": to_date,
        "token": FINNHUB_API_TOKEN
    }

    try:
        resp = get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("earningsCalendar", [])
    except Exception:
        return []


def get_target_month() -> tuple[int, int]:
    today = date.today()

    env_year = environ.get("YEAR")
    env_month = environ.get("MONTH")

    if env_year and env_month:
        return int(env_year), int(env_month)

    if today.month == 12:
        return today.year + 1, 1
    else:
        return today.year, today.month + 1


def has_more_pages(rows: list) -> bool:
    return len(rows) >= ROWS_PER_PAGE


def is_valid_earnings_date(earnings_date: str) -> bool:
    try:
        date_obj = date.fromisoformat(earnings_date)
        return not is_weekend(date_obj)
    except:
        return False


def is_weekend(date_obj: date) -> bool:
    return date_obj.weekday() >= 5


def lambda_handler(event, context):
    try:
        year, month = get_target_month()
        days_in_month = monthrange(year, month)[1]

        records = []
        nasdaq_symbols = set()

        records, nasdaq_symbols = process_nasdaq_earnings(year, month, days_in_month, records, nasdaq_symbols)

        from_date = f"{year}-{month:02}-01"
        to_date = f"{year}-{month:02}-{days_in_month:02}"

        records = process_finnhub_earnings(from_date, to_date, nasdaq_symbols, records)

        df = convert_to_dataframe(records)
        csv_data = df.to_csv(index=False)

        s3_key = build_s3_key(year, month)
        upload_to_s3(s3_key, csv_data)

        nasdaq_count, finnhub_count = calculate_source_counts(records)

        return {
            "statusCode": 200,
            "body": {
                "message": "Success",
                "records_uploaded": len(df),
                "nasdaq_records": nasdaq_count,
                "finnhub_records": finnhub_count,
                "s3_bucket": S3_BUCKET,
                "s3_key": s3_key
            }
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": f"Error: {str(e)}"
        }


def process_finnhub_earnings(from_date: str, to_date: str, nasdaq_symbols: set, records: list) -> list:
    finnhub_data = fetch_finnhub_earnings(from_date, to_date)

    for item in finnhub_data:
        symbol = item.get("symbol")
        earnings_date = item.get("date")

        if symbol in nasdaq_symbols:
            continue

        if not is_valid_earnings_date(earnings_date):
            continue

        record = build_finnhub_earnings_record(item, symbol, earnings_date)
        records.append(record)

    return records


def process_nasdaq_earnings(year: int, month: int, days_in_month: int, records: list, nasdaq_symbols: set) -> tuple[list, set]:
    for day in range(1, days_in_month + 1):
        current_date = date(year, month, day)

        if is_weekend(current_date):
            continue

        try:
            rows = fetch_earnings_for_day(year, month, day)
        except Exception:
            continue

        for item in rows:
            symbol = item.get("symbol")
            nasdaq_symbols.add(symbol)
            record = build_nasdaq_earnings_record(item, current_date)
            records.append(record)

    return records, nasdaq_symbols


def upload_to_s3(s3_key: str, csv_data: str) -> None:
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=csv_data,
        ContentType="text/csv"
    )


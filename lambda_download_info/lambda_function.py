from calendar import monthrange
from datetime import date
from os import environ
from boto3 import client
from pandas import DataFrame
from requests import get

HEADERS = {"User-Agent": "Mozilla/5.0"}
ROWS_PER_PAGE = 1000
S3_BUCKET = environ.get("S3_BUCKET")

s3 = client("s3")

def get_target_month():
    """Return the year/month to process, based on env vars or next month."""
    today = date.today()

    env_year = environ.get("YEAR")
    env_month = environ.get("MONTH")

    if env_year and env_month:
        return int(env_year), int(env_month)

    if today.month == 12:
        return today.year + 1, 1
    else:
        return today.year, today.month + 1


def fetch_earnings_for_day(year: int, month: int, day: int):
    """Fetch and return all earnings rows for one specific day, handling pagination."""
    all_rows = []
    offset = 0

    while True:
        url = f"https://api.nasdaq.com/api/calendar/earnings"
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

        if len(rows) < ROWS_PER_PAGE:
            break

        offset += ROWS_PER_PAGE

    return all_rows


def lambda_handler(event, context):
    try:
        year, month = get_target_month()
        days_in_month = monthrange(year, month)[1]

        records = []

        for day in range(1, days_in_month + 1):
            current_date = date(year, month, day)

            if current_date.weekday() >= 5:
                continue

            try:
                rows = fetch_earnings_for_day(year, month, day)
            except Exception as e:
                continue

            for item in rows:
                records.append({
                    "Company": item.get("name"),
                    "Date": current_date.isoformat(),
                    "EPS Estimate": item.get("epsForecast"),
                    "Market Cap": item.get("marketCap"),
                    "Symbol": item.get("symbol"),
                    "Time": item.get("time")
                })

        df = DataFrame(records)
        csv_data = df.to_csv(index=False)

        s3_key = f"{year}/{month:02}/earnings.csv"

        s3.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=csv_data,
            ContentType="text/csv"
        )

        return {
            "statusCode": 200,
            "body": {
                "message": "Success",
                "records_uploaded": len(df),
                "s3_bucket": S3_BUCKET,
                "s3_key": s3_key
            }
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": f"Error: {str(e)}"
        }

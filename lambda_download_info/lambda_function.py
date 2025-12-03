from calendar import monthrange
from datetime import date
from os import environ
from pandas import DataFrame

from boto3 import client
from requests import get

HEADERS = {"User-Agent": "Mozilla/5.0"}
ROWS_PER_PAGE = 1000
S3_BUCKET: str = environ.get("S3_BUCKET")

s3_client = client("s3")
today = date.today()

year = today.year + (1 if today.month == 12 else 0)
month = today.month + 1 if today.month < 12 else 1
days_in_next_month = monthrange(today.year + 1, 1)[1] if today.month == 12 else monthrange(today.year + 1, 1)[1]

def lambda_handler(event, context):

    data = []
    start = 0

    try:

        for day in range(1, days_in_next_month + 1):

            if (current_day := date(year, month, day)).weekday() >= 5:
                print(f"Skipping weekend: {current_day}")
                continue

            params = {"date": "", "type": "earning", "limit": ROWS_PER_PAGE, "offset": start}

            response = get(f"https://api.nasdaq.com/api/calendar/earnings?date={year}-{month:02}-{day:02}", headers=HEADERS, params=params)
            response.raise_for_status()
            data_json = response.json()

            try:
                rows = data_json.get("data", {}).get("rows", [])
            except AttributeError as e:
                print(f"Error parsing JSON for date {current_day}: {e}")
                continue

            if not rows:
                continue

            for item in rows:
                data.append(
                    {
                        "Company": item.get("name"),
                        "Date": current_day,
                        "EPS Estimate": item.get("epsForecast"),
                        "Market Cap": item.get("marketCap"),
                        "Symbol": item.get("symbol"),
                        "Time": item.get("time")
                    }
                )

            start += ROWS_PER_PAGE

        df = DataFrame(data)
        df.to_csv("nasdaq_earnings_next_month.csv", index=False)
        print(f"Saved {len(df)} rows")

        return {
            'statusCode': 200,
            'body': {
                'records_uploaded': len(df),
                'message': 'Successfully uploaded earnings data',
                's3_bucket': S3_BUCKET,
                's3_key': f'{year}/{month}/companies.csv'
            }
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': f'Error: {str(e)}'
        }

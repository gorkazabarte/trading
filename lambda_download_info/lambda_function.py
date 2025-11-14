from csv import reader
from datetime import datetime
from json import dumps
from os import environ

from boto3 import client
from requests import Session

API_KEY = environ.get('API_KEY')
CSV_URL = f'https://www.alphavantage.co/query?function=EARNINGS_CALENDAR&horizon=3month&apikey={API_KEY}'
S3_BUCKET: str = environ.get("S3_BUCKET")

s3_client = client("s3")

def lambda_handler(event, context):

    try:
        today_str = datetime.today().strftime('%Y-%m-%d')

        with Session() as s:
            download = s.get(CSV_URL)
            decoded_content = download.content.decode('utf-8')
            cr = reader(decoded_content.splitlines(), delimiter=',')
            data_list = list(cr)

        headers = data_list[0]
        rows = data_list[1:]
        json_data = [dict(zip(headers, row)) for row in rows]

        today_data = [row for row in json_data if row.get('reportDate') == today_str]
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=f'earnings_{today_str}.json',
            Body=dumps(today_data, ensure_ascii=False, indent=2),
            ContentType="application/json"
        )

        return {
            'statusCode': 200,
            'body': 'Earnings data for today uploaded to S3.'
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': f'Error: {str(e)}'
        }

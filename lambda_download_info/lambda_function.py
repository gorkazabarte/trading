from csv import reader
from datetime import datetime
from json import dumps
from os import environ

from requests import Session

API_KEY = environ.get('API_KEY')
CSV_URL = f'https://www.alphavantage.co/query?function=EARNINGS_CALENDAR&horizon=3month&apikey={API_KEY}'

def lambda_handler(event, context):
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

    return {
        'statusCode': 200,
        'body': dumps(today_data, indent=4)
    }

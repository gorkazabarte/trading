from datetime import datetime, timezone
from json import loads
from logging import INFO
import os

from boto3 import client

from ibkr.contract_details import contract_search
from ibkr.historical_data import get_market_snapshot
from ibkr.order_request import order_request
from logs.setup import (setup_logging)

now = datetime.now(timezone.utc)
year = now.year
month = now.month
day = now.day

s3 = client('s3')
s3_bucket = 'dev-trading-data-storage'

if __name__ == "__main__":

    logger = setup_logging(log_file='logs/app.log', log_level=INFO)
    logger.info("Trading application has started successfully.")

    os.makedirs(f'./files/{year}/{month}/{day}', exist_ok=True)
    os.makedirs('./files', exist_ok=True)
    logger.info("Directories created successfully.")

    s3.download_file(s3_bucket, 'settings.json', './files/settings.json')
    s3.download_file(s3_bucket, f'{year}/{month}/{day}/selected_companies.txt', f'./files/{year}/{month}/{day}/selected_companies.txt')
    logger.info("Files downloaded successfully.")

    with open('./files/settings.json', 'r') as f:
        settings_content = loads(f.read())
        logger.info(f"Settings content: {settings_content}")

    with open(f'./files/{year}/{month}/{day}/selected_companies.txt', 'r') as f:
        companies_content = f.read().splitlines()
        logger.info(f"Selected companies content: {companies_content}")

    for company in companies_content:
        conid = contract_search(company)
        logger.info(f"Contract ID for {company}: {conid}")

        snapshot = get_market_snapshot(int(conid))
        logger.info(f"Market snapshot for {company}: {snapshot}")

        if snapshot and len(snapshot) > 0:
            market_data = snapshot[0]
            current_price = market_data.get('31')  # Field 31 = Last Price
            bid_price = market_data.get('84')      # Field 84 = Bid Price
            ask_price = market_data.get('86')      # Field 86 = Ask Price
            volume = market_data.get('87')         # Field 87 = Volume

            logger.info(f"{company} - Current Price: ${current_price}, Bid: ${bid_price}, Ask: ${ask_price}, Volume: {volume}")

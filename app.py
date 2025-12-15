from datetime import datetime, timezone, timedelta
from json import dumps, loads
from logging import INFO, Logger
from os import makedirs, path
from time import sleep
from typing import Dict, List, Optional

from boto3 import client

from ibkr.contract_details import contract_search
from ibkr.historical_data import get_market_snapshot
from ibkr.market_data_parser import format_market_data_log, parse_market_data
from logs.setup import setup_logging

S3_BUCKET = 'dev-trading-data-storage'
UPDATE_INTERVAL = 5


def create_company_data(ticker: str, parsed_data: Dict, closing_price: Optional[str], year: int, month: int, day: int) -> Dict:
    now = datetime.now(timezone.utc)

    return {
        'ticker': ticker,
        'timestamp': now.isoformat(),
        'date': f"{year}-{month:02d}-{day:02d}",
        'conid': parsed_data.get('conid'),
        'last_price': parsed_data.get('last_price'),
        'closing_price': closing_price,
        'bid_price': parsed_data.get('bid_price'),
        'ask_price': parsed_data.get('ask_price'),
        'volume': parsed_data.get('volume'),
        'volume_raw': parsed_data.get('volume_raw'),
        'spread': parsed_data.get('spread'),
        'spread_percent': parsed_data.get('spread_percent'),
        'is_market_closed': parsed_data.get('is_market_closed'),
        'price_type': parsed_data.get('price_type'),
        'exchange_code': parsed_data.get('exchange_code')
    }


def create_directories(year: int, month: int, day: int) -> str:
    market_data_dir = f'./files/{year}/{month}/{day}'
    makedirs(market_data_dir, exist_ok=True)
    makedirs('./files', exist_ok=True)
    return market_data_dir


def determine_closing_price(parsed_data: Dict, existing_closing_price: Optional[str], logger: Logger, ticker: str) -> Optional[str]:
    if should_preserve_existing_closing_price(existing_closing_price):
        logger.info(f"{ticker} - Preserving existing closing price: ${existing_closing_price}")
        return existing_closing_price

    if is_official_closing_price(parsed_data):
        closing_price = parsed_data.get('last_price')
        logger.info(f"{ticker} - Setting closing price: ${closing_price}")
        return closing_price

    if has_previous_close(parsed_data):
        closing_price = parsed_data.get('previous_close')
        logger.info(f"{ticker} - Setting closing price from previous_close: ${closing_price}")
        return closing_price

    return None


def download_companies_list(s3_client, bucket: str, year: int, month: int, day: int, logger: Logger) -> Optional[List[str]]:
    try:
        file_path = f'./files/{year}/{month}/{day}/selected_companies.txt'
        s3_client.download_file(bucket, f'{year}/{month}/{day}/selected_companies.txt', file_path)
        with open(file_path, 'r') as f:
            return f.read().splitlines()
    except Exception as e:
        logger.error(f"Companies were not selected for {year}/{month}/{day}.")
        return None


def download_settings_file(s3_client, bucket: str, logger: Logger) -> Optional[Dict]:
    try:
        s3_client.download_file(bucket, 'settings.json', './files/settings.json')
        with open('./files/settings.json', 'r') as f:
            return loads(f.read())
    except Exception as e:
        logger.error(f"Failed to download settings.json: {e}")
        return None


def fetch_and_parse_market_data(ticker: str, logger: Logger) -> Optional[Dict]:
    try:
        conid = contract_search(ticker)
        logger.info(f"Contract ID for {ticker}: {conid}")

        snapshot = get_market_snapshot(int(conid))

        if not is_valid_snapshot(snapshot):
            logger.warning(f"{ticker} - Empty or invalid snapshot response")
            return None

        market_data = snapshot[0]
        parsed_data = parse_market_data(market_data)
        logger.info(format_market_data_log(ticker, parsed_data))

        return parsed_data

    except Exception as e:
        logger.error(f"{ticker} - Error fetching market data: {e}")
        return None


def get_current_date() -> tuple[int, int, int]:
    now = datetime.now(timezone.utc)
    return now.year, now.month, now.day


def get_existing_closing_price(file_path: str, logger: Logger) -> Optional[str]:
    if not path.exists(file_path):
        return None

    try:
        with open(file_path, 'r') as f:
            existing_data = loads(f.read())
            return existing_data.get('closing_price')
    except Exception as e:
        logger.warning(f"Could not read existing file {file_path}: {e}")
        return None


def has_previous_close(parsed_data: Dict) -> bool:
    return parsed_data.get('previous_close') is not None


def has_required_dependencies(settings: Optional[Dict], companies: Optional[List[str]]) -> bool:
    return settings is not None and companies is not None


def is_official_closing_price(parsed_data: Dict) -> bool:
    return parsed_data.get('price_type') == 'Closing Price'


def is_valid_snapshot(snapshot: Optional[List]) -> bool:
    return snapshot is not None and len(snapshot) > 0


def log_next_update_time(update_interval: int, logger: Logger) -> None:
    next_update = datetime.now(timezone.utc) + timedelta(seconds=update_interval)
    logger.info(f"Next update at: {next_update.strftime('%Y-%m-%d %H:%M:%S UTC')}")


def main():
    logger = setup_logging(log_file='logs/app.log', log_level=INFO)
    s3_client = client('s3')

    logger.info("Trading application has started successfully.")
    logger.info(f"Market data will update every {UPDATE_INTERVAL} seconds")

    while True:
        success = run_market_data_collection_cycle(s3_client, logger)

        if success:
            log_next_update_time(UPDATE_INTERVAL, logger)

        sleep(UPDATE_INTERVAL)


def process_all_companies(companies: List[str], market_data_dir: str, year: int, month: int, day: int, logger: Logger) -> None:
    logger.info(f"Updating market data for {len(companies)} companies...")

    for company in companies:
        process_company(company, market_data_dir, year, month, day, logger)


def process_company(ticker: str, market_data_dir: str, year: int, month: int, day: int, logger: Logger) -> bool:
    parsed_data = fetch_and_parse_market_data(ticker, logger)
    if parsed_data is None:
        return False

    file_path = f"{market_data_dir}/{ticker}.json"
    existing_closing_price = get_existing_closing_price(file_path, logger)

    closing_price = determine_closing_price(parsed_data, existing_closing_price, logger, ticker)
    company_data = create_company_data(ticker, parsed_data, closing_price, year, month, day)

    return save_company_data(file_path, company_data, logger, ticker)


def run_market_data_collection_cycle(s3_client, logger: Logger) -> bool:
    year, month, day = get_current_date()
    market_data_dir = create_directories(year, month, day)

    settings = download_settings_file(s3_client, S3_BUCKET, logger)
    companies = download_companies_list(s3_client, S3_BUCKET, year, month, day, logger)

    if not has_required_dependencies(settings, companies):
        return False

    process_all_companies(companies, market_data_dir, year, month, day, logger)

    return True


def save_company_data(file_path: str, company_data: Dict, logger: Logger, ticker: str) -> bool:
    try:
        with open(file_path, 'w') as f:
            f.write(dumps(company_data, indent=2))
        logger.info(f"{ticker} - Market data saved to: {file_path}")
        return True
    except Exception as e:
        logger.error(f"{ticker} - Failed to save market data: {e}")
        return False


def should_preserve_existing_closing_price(existing_closing_price: Optional[str]) -> bool:
    return existing_closing_price is not None


if __name__ == "__main__":
    main()


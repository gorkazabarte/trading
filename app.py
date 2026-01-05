"""
Main trading application entry point.
Orchestrates the trading workflow using modular components.
"""
from logging import INFO, Logger
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

from core.config import S3_BUCKET
from core.state import mark_files_as_downloaded, get_closed_positions
from utils.aws_client import create_s3_client
from utils.time_utils import get_current_date, should_exit_at_market_close, is_close_to_market_close
from utils.file_operations import download_companies_list, download_settings_file
from trading.sell_orders import handle_end_of_day_sales
from trading.market_data import run_market_data_collection_cycle, log_positions_summary
from services.ibkr.ib_gateway_client import get_ib_client, disconnect_ib_client
from services.ibkr.ib_portfolio import fetch_and_sync_positions, save_closed_positions_to_s3
from logs.setup import setup_logging

disable_warnings(InsecureRequestWarning)


def download_daily_files(s3_client, bucket: str, year: int, month: int, day: int, logger: Logger):
    logger.info("=" * 60)
    logger.info("DOWNLOADING DAILY FILES FROM S3")
    logger.info("=" * 60)

    settings = download_settings_file(s3_client, bucket, logger)
    companies = download_companies_list(s3_client, bucket, year, month, day, logger)

    if settings and companies:
        mark_files_as_downloaded()
        logger.info("Successfully downloaded all daily files")
        logger.info("=" * 60)
        return settings, companies

    logger.error("Failed to download one or more daily files")
    return None, None


def place_initial_orders(s3_client, logger: Logger):
    logger.info("=" * 60)
    logger.info("FIRST ITERATION - PLACING ORDERS")
    logger.info("=" * 60)

    fetch_and_sync_positions(logger, s3_client)
    market_data_by_ticker = run_market_data_collection_cycle(s3_client, logger)

    if market_data_by_ticker:
        from core.state import get_bought_shares
        logger.info(f"Orders placed for {len(get_bought_shares())} companies")
        log_positions_summary(market_data_by_ticker, logger)
    else:
        logger.warning("No market data collected during first iteration")

    logger.info("=" * 60)
    return market_data_by_ticker or {}


def monitor_prices_and_positions(s3_client, logger: Logger):
    logger.info("=" * 60)
    logger.info("MONITORING MODE - Tracking positions until market close")
    logger.info("=" * 60)

    while not should_exit_at_market_close():
        try:
            fetch_and_sync_positions(logger, s3_client)
            market_data_by_ticker = run_market_data_collection_cycle(s3_client, logger)

            if market_data_by_ticker:
                handle_end_of_day_sales(logger)

                if is_close_to_market_close() and len(get_closed_positions()) > 0:
                    year, month, day = get_current_date()
                    save_closed_positions_to_s3(year, month, day, s3_client, logger)

                log_positions_summary(market_data_by_ticker, logger)

        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")


def initialize_trading_session(logger: Logger):
    try:
        s3_client = create_s3_client()
        logger.info("Trading application has started successfully.")
        return s3_client
    except Exception as e:
        logger.error(f"Failed to create S3 client: {e}")
        exit(1)


def download_required_files(s3_client, logger: Logger):
    year, month, day = get_current_date()
    settings, companies = download_daily_files(s3_client, S3_BUCKET, year, month, day, logger)

    if not settings or not companies:
        logger.error("Failed to download required files. Application cannot start.")
        exit(1)

    return settings, companies


def connect_to_ib_gateway(logger: Logger):
    logger.info("Connecting to IB Gateway for real-time market data...")
    ib_client = get_ib_client()

    if ib_client.connected:
        logger.info("IB Gateway connected - Real-time market data is available")
        return ib_client
    else:
        logger.error("Failed to connect to IB Gateway. Make sure IB Gateway is running on port 4001.")
        exit(1)


def run_trading_workflow(s3_client, logger: Logger):
    try:
        place_initial_orders(s3_client, logger)
        monitor_prices_and_positions(s3_client, logger)

        logger.info("Market is closed. Exiting program with status 0.")
        disconnect_ib_client()
        exit(0)

    except KeyboardInterrupt:
        logger.info("Program interrupted by user. Cleaning up...")
        disconnect_ib_client()
        exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        disconnect_ib_client()
        exit(1)


def run_trading_application():
    from datetime import datetime, timezone

    current_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    log_filename = f'logs/{current_date}.log'
    logger = setup_logging(log_file=log_filename, log_level=INFO)

    s3_client = initialize_trading_session(logger)
    download_required_files(s3_client, logger)
    connect_to_ib_gateway(logger)
    run_trading_workflow(s3_client, logger)


if __name__ == "__main__":
    run_trading_application()

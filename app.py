from datetime import datetime, timezone
from logging import INFO, Logger
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

from core.config import S3_BUCKET
from logs.setup import setup_logging
from services.ibkr.ib_gateway_client import disconnect_ib_client
from utils.aws_client import create_s3_client, upload_status_to_s3
from workflow.connection import connect_to_ib_gateway
from workflow.download import download_required_files
from workflow.initial_orders import place_initial_orders
from workflow.monitoring import monitor_prices_and_positions, log_market_closed_exit

disable_warnings(InsecureRequestWarning)


def handle_keyboard_interrupt(logger: Logger):
    logger.info("Program interrupted by user. Cleaning up...")
    disconnect_ib_client()
    exit(0)


def handle_unexpected_error(logger: Logger, error: Exception):
    logger.error(f"Unexpected error: {error}")
    disconnect_ib_client()
    exit(1)


def initialize_trading_session(logger: Logger):
    try:
        s3_client = create_s3_client()
        logger.info("Trading application has started successfully.")
        return s3_client
    except Exception as e:
        logger.error(f"Failed to create S3 client: {e}")
        exit(1)


def run_trading_application():
    current_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    log_filename = f'logs/{current_date}.log'
    logger = setup_logging(log_file=log_filename, log_level=INFO)

    s3_client = initialize_trading_session(logger)
    download_required_files(s3_client, S3_BUCKET, logger)
    connect_to_ib_gateway(logger)
    run_trading_workflow(s3_client, logger)


def run_trading_workflow(s3_client, logger: Logger):
    try:
        place_initial_orders(s3_client, logger)
        monitor_prices_and_positions(s3_client, logger)

        log_market_closed_exit(logger)
        upload_status_to_s3(s3_client, S3_BUCKET, "End")
        disconnect_ib_client()
        exit(0)

    except KeyboardInterrupt:
        handle_keyboard_interrupt(logger)
    except Exception as e:
        handle_unexpected_error(logger, e)



if __name__ == "__main__":
    run_trading_application()

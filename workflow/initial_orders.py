"""
Initial order placement workflow.
"""
from logging import Logger

from core.config import S3_BUCKET
from services.ibkr.ib_portfolio import fetch_and_sync_positions
from trading.market_data import run_market_data_collection_cycle, log_positions_summary
from utils.aws_client import upload_status_to_s3


def collect_initial_market_data(s3_client, logger: Logger):
    fetch_and_sync_positions(logger, s3_client)
    return run_market_data_collection_cycle(s3_client, logger)


def log_first_iteration_footer(logger: Logger):
    logger.info("=" * 60)


def log_first_iteration_header(logger: Logger):
    logger.info("=" * 60)
    logger.info("FIRST ITERATION - PLACING ORDERS")
    logger.info("=" * 60)


def log_orders_placed(logger: Logger):
    from core.state import get_bought_shares
    logger.info(f"Orders placed for {len(get_bought_shares())} companies")


def place_initial_orders(s3_client, logger: Logger):
    upload_status_to_s3(s3_client, S3_BUCKET, "Init")

    log_first_iteration_header(logger)

    market_data_by_ticker = collect_initial_market_data(s3_client, logger)

    if market_data_by_ticker:
        log_orders_placed(logger)
        log_positions_summary(market_data_by_ticker, logger)
    else:
        logger.warning("No market data collected during first iteration")

    log_first_iteration_footer(logger)
    return market_data_by_ticker or {}


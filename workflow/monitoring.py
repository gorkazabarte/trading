"""
Monitoring workflow for tracking positions and market data.
"""
from logging import Logger
from time import sleep

from services.ibkr.ib_portfolio import fetch_and_sync_positions, update_order_fill_status, log_order_statuses, update_market_prices
from trading.market_data import run_market_data_collection_cycle, log_positions_summary
from trading.sell_orders import handle_end_of_day_sales
from utils.time_utils import should_exit_at_market_close, is_close_to_market_close
from workflow.cleanup import verify_cleanup
from workflow.reconciliation import save_closed_positions_if_exist


def fetch_current_state(logger: Logger, s3_client):
    fetch_and_sync_positions(logger, s3_client)
    update_order_fill_status(logger, s3_client)


def handle_end_of_day_verification(logger: Logger, s3_client):
    handle_end_of_day_sales(logger, s3_client)
    verification_passed = verify_cleanup(logger, s3_client)

    if verification_passed:
        log_cleanup_success(logger)
        save_closed_positions_if_exist(s3_client, logger)
        return True
    else:
        log_cleanup_failure(logger)
        return False


def log_cleanup_failure(logger: Logger):
    logger.error("=" * 60)
    logger.error("END-OF-DAY CLEANUP FAILED")
    logger.error("Manual intervention required")
    logger.error("=" * 60)


def log_cleanup_success(logger: Logger):
    logger.info("=" * 60)
    logger.info("END-OF-DAY CLEANUP SUCCESSFUL")
    logger.info("All positions closed and all orders cancelled")
    logger.info("Application completed successfully")
    logger.info("=" * 60)


def log_market_closed_exit(logger: Logger):
    logger.info("Market is closed. Exiting program with status 0.")


def log_monitoring_header(logger: Logger):
    logger.info("=" * 60)
    logger.info("MONITORING MODE - Tracking positions until market close")
    logger.info("=" * 60)


def monitor_prices_and_positions(s3_client, logger: Logger):
    from core.state import disable_order_placement, set_closing_phase, is_in_closing_phase

    log_monitoring_header(logger)

    disable_order_placement()
    logger.info("Order placement disabled - monitoring mode active")

    end_of_day_executed = False

    while should_continue_monitoring():
        try:
            if is_close_to_market_close() and not is_in_closing_phase():
                set_closing_phase()
                logger.info("=" * 60)
                logger.info("ENTERING CLOSING PHASE - No new orders will be placed")
                logger.info("=" * 60)

            fetch_current_state(logger, s3_client)
            market_data_by_ticker = run_market_data_collection_cycle(s3_client, logger)

            if market_data_by_ticker:
                end_of_day_executed = process_market_data(s3_client, logger, market_data_by_ticker, end_of_day_executed)

            sleep_one_minute()

        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")


def process_market_data(s3_client, logger: Logger, market_data_by_ticker: dict, end_of_day_executed: bool) -> bool:
    update_and_log_market_data(s3_client, logger, market_data_by_ticker)

    if should_execute_end_of_day(end_of_day_executed):
        handle_end_of_day_verification(logger, s3_client)
        return True

    save_closed_positions_if_exist(s3_client, logger)
    log_positions_summary(market_data_by_ticker, logger)
    return end_of_day_executed


def should_continue_monitoring() -> bool:
    return not should_exit_at_market_close()


def should_execute_end_of_day(end_of_day_executed: bool) -> bool:
    return is_close_to_market_close() and not end_of_day_executed


def sleep_one_minute():
    sleep(60)


def update_and_log_market_data(s3_client, logger: Logger, market_data_by_ticker: dict):
    update_market_prices(logger, s3_client, market_data_by_ticker)
    log_order_statuses(logger, market_data_by_ticker)


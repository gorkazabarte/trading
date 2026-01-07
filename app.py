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
from services.ibkr.ib_portfolio import fetch_and_sync_positions, save_closed_positions_to_s3, update_order_fill_status, log_order_statuses, update_market_prices
from logs.setup import setup_logging

disable_warnings(InsecureRequestWarning)


def log_download_header(logger: Logger):
    logger.info("=" * 60)
    logger.info("DOWNLOADING DAILY FILES FROM S3")
    logger.info("=" * 60)


def log_download_footer(logger: Logger):
    logger.info("=" * 60)


def download_files_from_s3(s3_client, bucket: str, year: int, month: int, day: int, logger: Logger):
    settings = download_settings_file(s3_client, bucket, logger)
    companies = download_companies_list(s3_client, bucket, year, month, day, logger)
    return settings, companies


def are_files_downloaded(settings, companies) -> bool:
    return settings and companies


def mark_downloads_complete(logger: Logger):
    mark_files_as_downloaded()
    logger.info("Successfully downloaded all daily files")


def download_daily_files(s3_client, bucket: str, year: int, month: int, day: int, logger: Logger):
    log_download_header(logger)

    settings, companies = download_files_from_s3(s3_client, bucket, year, month, day, logger)

    if are_files_downloaded(settings, companies):
        mark_downloads_complete(logger)
        log_download_footer(logger)
        return settings, companies

    logger.error("Failed to download one or more daily files")
    return None, None


def log_first_iteration_header(logger: Logger):
    logger.info("=" * 60)
    logger.info("FIRST ITERATION - PLACING ORDERS")
    logger.info("=" * 60)


def log_first_iteration_footer(logger: Logger):
    logger.info("=" * 60)


def log_orders_placed(logger: Logger):
    from core.state import get_bought_shares
    logger.info(f"Orders placed for {len(get_bought_shares())} companies")


def collect_initial_market_data(s3_client, logger: Logger):
    fetch_and_sync_positions(logger, s3_client)
    return run_market_data_collection_cycle(s3_client, logger)


def place_initial_orders(s3_client, logger: Logger):
    log_first_iteration_header(logger)

    market_data_by_ticker = collect_initial_market_data(s3_client, logger)

    if market_data_by_ticker:
        log_orders_placed(logger)
        log_positions_summary(market_data_by_ticker, logger)
    else:
        logger.warning("No market data collected during first iteration")

    log_first_iteration_footer(logger)
    return market_data_by_ticker or {}


def log_retry_header(logger: Logger):
    logger.info("=" * 60)
    logger.info("RETRYING CLEANUP - Closing remaining positions and orders")
    logger.info("=" * 60)


def log_retry_footer(logger: Logger):
    logger.info("=" * 60)


def cancel_remaining_orders(ib_client, logger: Logger):
    cancel_result = ib_client.cancel_all_orders()
    if not cancel_result.get('success'):
        return

    cancelled_count = cancel_result.get('cancelled_count', 0)
    if cancelled_count > 0:
        logger.info(f"Cancelled {cancelled_count} additional pending order(s)")
    else:
        logger.info("No additional pending orders to cancel")


def close_remaining_positions(ib_client, logger: Logger):
    positions = ib_client.get_positions()

    if positions and len(positions) > 0:
        logger.info(f"Found {len(positions)} position(s) to close")
        from trading.sell_orders import close_positions
        close_positions(positions, logger)
    else:
        logger.info("No additional positions to close")


def is_ib_connected(ib_client, logger: Logger) -> bool:
    if not ib_client.connected:
        logger.error("IB Gateway not connected - cannot retry cleanup")
        return False
    return True


def retry_cleanup(logger: Logger, s3_client):
    log_retry_header(logger)

    ib_client = get_ib_client()

    if not is_ib_connected(ib_client, logger):
        return False

    cancel_remaining_orders(ib_client, logger)
    close_remaining_positions(ib_client, logger)

    log_retry_footer(logger)
    return True


def log_verification_header(logger: Logger):
    logger.info("=" * 60)
    logger.info("VERIFICATION - Waiting 2 minutes before final check")
    logger.info("=" * 60)


def log_verification_footer(logger: Logger):
    logger.info("=" * 60)


def wait_for_cleanup(logger: Logger):
    from time import sleep
    sleep(120)


def wait_for_reverification(logger: Logger):
    from time import sleep
    logger.info("Waiting 30 seconds before re-verification...")
    sleep(30)


def get_verification_results(ib_client):
    positions_result = ib_client.verify_no_open_positions()
    orders_result = ib_client.verify_no_open_orders()
    return positions_result, orders_result


def are_results_valid(positions_result: dict, orders_result: dict) -> bool:
    return positions_result.get('success') and orders_result.get('success')


def extract_counts(positions_result: dict, orders_result: dict) -> tuple:
    open_positions_count = positions_result.get('open_positions_count', 0)
    open_orders_count = orders_result.get('open_orders_count', 0)
    return open_positions_count, open_orders_count


def log_verification_counts(open_positions_count: int, open_orders_count: int, logger: Logger):
    logger.info(f"Open positions: {open_positions_count}")
    logger.info(f"Open orders: {open_orders_count}")


def log_reverification_counts(open_positions_count: int, open_orders_count: int, logger: Logger):
    logger.info(f"Re-verification - Open positions: {open_positions_count}")
    logger.info(f"Re-verification - Open orders: {open_orders_count}")


def is_cleanup_complete(open_positions_count: int, open_orders_count: int) -> bool:
    return open_positions_count == 0 and open_orders_count == 0


def log_verification_success(logger: Logger):
    logger.info("✓ VERIFICATION PASSED - No open positions or orders")
    log_verification_footer(logger)


def log_verification_failures(open_positions_count: int, open_orders_count: int, logger: Logger):
    if open_positions_count > 0:
        logger.error(f"✗ VERIFICATION FAILED - {open_positions_count} position(s) still open")
    if open_orders_count > 0:
        logger.error(f"✗ VERIFICATION FAILED - {open_orders_count} order(s) still open")
    log_verification_footer(logger)


def log_reverification_success(logger: Logger):
    logger.info("✓ RE-VERIFICATION PASSED - All positions and orders closed")
    log_verification_footer(logger)


def log_reverification_failure(logger: Logger):
    logger.error("✗ RE-VERIFICATION FAILED - Manual intervention required")
    log_verification_footer(logger)


def perform_reverification(ib_client, logger: Logger) -> bool:
    wait_for_reverification(logger)

    positions_result_2, orders_result_2 = get_verification_results(ib_client)

    if not are_results_valid(positions_result_2, orders_result_2):
        return False

    open_positions_count_2, open_orders_count_2 = extract_counts(positions_result_2, orders_result_2)
    log_reverification_counts(open_positions_count_2, open_orders_count_2, logger)

    if is_cleanup_complete(open_positions_count_2, open_orders_count_2):
        log_reverification_success(logger)
        return True
    else:
        log_reverification_failure(logger)
        return False


def handle_verification_failure(ib_client, logger: Logger, s3_client) -> bool:
    retry_cleanup(logger, s3_client)
    return perform_reverification(ib_client, logger)


def verify_cleanup(logger: Logger, s3_client):
    log_verification_header(logger)
    wait_for_cleanup(logger)

    logger.info("Verifying all positions and orders are closed...")

    ib_client = get_ib_client()

    if not ib_client.connected:
        logger.error("IB Gateway not connected - cannot verify cleanup")
        return False

    positions_result, orders_result = get_verification_results(ib_client)

    if not are_results_valid(positions_result, orders_result):
        logger.error("Failed to verify cleanup")
        return False

    open_positions_count, open_orders_count = extract_counts(positions_result, orders_result)
    log_verification_counts(open_positions_count, open_orders_count, logger)

    if is_cleanup_complete(open_positions_count, open_orders_count):
        log_verification_success(logger)
        return True
    else:
        log_verification_failures(open_positions_count, open_orders_count, logger)
        return handle_verification_failure(ib_client, logger, s3_client)


def log_monitoring_header(logger: Logger):
    logger.info("=" * 60)
    logger.info("MONITORING MODE - Tracking positions until market close")
    logger.info("=" * 60)


def should_continue_monitoring() -> bool:
    return not should_exit_at_market_close()


def fetch_current_state(logger: Logger, s3_client):
    fetch_and_sync_positions(logger, s3_client)
    update_order_fill_status(logger, s3_client)


def update_and_log_market_data(s3_client, logger: Logger, market_data_by_ticker: dict):
    update_market_prices(logger, s3_client, market_data_by_ticker)
    log_order_statuses(logger, market_data_by_ticker)


def should_execute_end_of_day(end_of_day_executed: bool) -> bool:
    return is_close_to_market_close() and not end_of_day_executed


def log_cleanup_success(logger: Logger):
    logger.info("=" * 60)
    logger.info("END-OF-DAY CLEANUP SUCCESSFUL")
    logger.info("All positions closed and all orders cancelled")
    logger.info("Application completed successfully")
    logger.info("=" * 60)


def log_cleanup_failure(logger: Logger):
    logger.error("=" * 60)
    logger.error("END-OF-DAY CLEANUP FAILED")
    logger.error("Manual intervention required")
    logger.error("=" * 60)


def save_closed_positions_if_exist(s3_client, logger: Logger):
    if len(get_closed_positions()) > 0:
        year, month, day = get_current_date()
        save_closed_positions_to_s3(year, month, day, s3_client, logger)


def exit_with_success(logger: Logger, s3_client):
    log_cleanup_success(logger)
    save_closed_positions_if_exist(s3_client, logger)
    disconnect_ib_client()
    exit(0)


def exit_with_failure(logger: Logger):
    log_cleanup_failure(logger)
    disconnect_ib_client()
    exit(1)


def handle_end_of_day_verification(logger: Logger, s3_client):
    handle_end_of_day_sales(logger, s3_client)
    verification_passed = verify_cleanup(logger, s3_client)

    if verification_passed:
        exit_with_success(logger, s3_client)
    else:
        exit_with_failure(logger)


def process_market_data(s3_client, logger: Logger, market_data_by_ticker: dict, end_of_day_executed: bool) -> bool:
    update_and_log_market_data(s3_client, logger, market_data_by_ticker)

    if should_execute_end_of_day(end_of_day_executed):
        handle_end_of_day_verification(logger, s3_client)
        return True

    save_closed_positions_if_exist(s3_client, logger)
    log_positions_summary(market_data_by_ticker, logger)
    return end_of_day_executed


def sleep_one_minute():
    from time import sleep
    sleep(60)


def monitor_prices_and_positions(s3_client, logger: Logger):
    log_monitoring_header(logger)

    end_of_day_executed = False

    while should_continue_monitoring():
        try:
            fetch_current_state(logger, s3_client)
            market_data_by_ticker = run_market_data_collection_cycle(s3_client, logger)

            if market_data_by_ticker:
                end_of_day_executed = process_market_data(s3_client, logger, market_data_by_ticker, end_of_day_executed)

            sleep_one_minute()

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


def log_market_status(logger: Logger):
    from utils.time_utils import get_current_eastern_time, is_market_hours_now

    current_et_time = get_current_eastern_time()
    is_market_open = is_market_hours_now()
    logger.info(f"Current ET time: {current_et_time}")
    logger.info(f"Market status: {'OPEN' if is_market_open else 'CLOSED'}")


def wait_for_connection_establishment(logger: Logger):
    import time
    logger.info("Waiting 10 seconds for connection to fully establish...")
    time.sleep(10)
    logger.info("Connection ready. Proceeding with trading workflow.")


def establish_ib_connection(logger: Logger):
    ib_client = get_ib_client()

    if ib_client.connected:
        logger.info("IB Gateway connected - Real-time market data is available")
        logger.info(f"Connected to: {ib_client}")
        wait_for_connection_establishment(logger)
        return ib_client
    else:
        logger.error("Failed to connect to IB Gateway. Make sure IB Gateway is running on port 4001.")
        exit(1)


def connect_to_ib_gateway(logger: Logger):
    logger.info("Connecting to IB Gateway for real-time market data...")
    log_market_status(logger)
    return establish_ib_connection(logger)


def log_market_closed_exit(logger: Logger):
    logger.info("Market is closed. Exiting program with status 0.")


def handle_keyboard_interrupt(logger: Logger):
    logger.info("Program interrupted by user. Cleaning up...")
    disconnect_ib_client()
    exit(0)


def handle_unexpected_error(logger: Logger, error: Exception):
    logger.error(f"Unexpected error: {error}")
    disconnect_ib_client()
    exit(1)


def run_trading_workflow(s3_client, logger: Logger):
    try:
        place_initial_orders(s3_client, logger)
        monitor_prices_and_positions(s3_client, logger)

        log_market_closed_exit(logger)
        disconnect_ib_client()
        exit(0)

    except KeyboardInterrupt:
        handle_keyboard_interrupt(logger)
    except Exception as e:
        handle_unexpected_error(logger, e)


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

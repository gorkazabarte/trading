"""
End-of-day cleanup and verification operations.
"""
from logging import Logger
from time import sleep

from services.ibkr.ib_gateway_client import get_ib_client


def are_results_valid(positions_result: dict, orders_result: dict) -> bool:
    return positions_result.get('success') and orders_result.get('success')


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


def extract_counts(positions_result: dict, orders_result: dict) -> tuple:
    open_positions_count = positions_result.get('open_positions_count', 0)
    open_orders_count = orders_result.get('open_orders_count', 0)
    return open_positions_count, open_orders_count


def get_verification_results(ib_client):
    positions_result = ib_client.verify_no_open_positions()
    orders_result = ib_client.verify_no_open_orders()
    return positions_result, orders_result


def handle_verification_failure(ib_client, logger: Logger, s3_client) -> bool:
    retry_cleanup(logger, s3_client)
    return perform_reverification(ib_client, logger)


def is_cleanup_complete(open_positions_count: int, open_orders_count: int) -> bool:
    return open_positions_count == 0 and open_orders_count == 0


def is_ib_connected(ib_client, logger: Logger) -> bool:
    if not ib_client.connected:
        logger.error("IB Gateway not connected - cannot retry cleanup")
        return False
    return True


def log_reverification_counts(open_positions_count: int, open_orders_count: int, logger: Logger):
    logger.info(f"Re-verification - Open positions: {open_positions_count}")
    logger.info(f"Re-verification - Open orders: {open_orders_count}")


def log_reverification_failure(logger: Logger):
    logger.error("✗ RE-VERIFICATION FAILED - Manual intervention required")
    log_verification_footer(logger)


def log_reverification_success(logger: Logger):
    logger.info("✓ RE-VERIFICATION PASSED - All positions and orders closed")
    log_verification_footer(logger)


def log_retry_footer(logger: Logger):
    logger.info("=" * 60)


def log_retry_header(logger: Logger):
    logger.info("=" * 60)
    logger.info("RETRYING CLEANUP - Closing remaining positions and orders")
    logger.info("=" * 60)


def log_verification_counts(open_positions_count: int, open_orders_count: int, logger: Logger):
    logger.info(f"Open positions: {open_positions_count}")
    logger.info(f"Open orders: {open_orders_count}")


def log_verification_failures(open_positions_count: int, open_orders_count: int, logger: Logger):
    if open_positions_count > 0:
        logger.error(f"✗ VERIFICATION FAILED - {open_positions_count} position(s) still open")
    if open_orders_count > 0:
        logger.error(f"✗ VERIFICATION FAILED - {open_orders_count} order(s) still open")
    log_verification_footer(logger)


def log_verification_footer(logger: Logger):
    logger.info("=" * 60)


def log_verification_header(logger: Logger):
    logger.info("=" * 60)
    logger.info("VERIFICATION - Waiting 2 minutes before final check")
    logger.info("=" * 60)


def log_verification_success(logger: Logger):
    logger.info("✓ VERIFICATION PASSED - No open positions or orders")
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


def retry_cleanup(logger: Logger, s3_client):
    log_retry_header(logger)

    ib_client = get_ib_client()

    if not is_ib_connected(ib_client, logger):
        return False

    cancel_remaining_orders(ib_client, logger)
    close_remaining_positions(ib_client, logger)

    log_retry_footer(logger)
    return True


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


def wait_for_cleanup(logger: Logger):
    sleep(120)


def wait_for_reverification(logger: Logger):
    logger.info("Waiting 30 seconds before re-verification...")
    sleep(30)


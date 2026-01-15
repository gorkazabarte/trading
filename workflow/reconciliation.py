"""
Application workflow orchestration.
"""
from logging import Logger

from core.state import get_closed_positions
from services.ibkr.ib_gateway_client import get_ib_client
from trading.execution_reconciliation import generate_closed_positions_from_executions
from utils.time_utils import get_current_date


def get_ib_executions(logger: Logger):
    ib_client = get_ib_client()
    if not ib_client.connected:
        logger.warning("IB Gateway not connected - using estimated prices from state")
        return []
    return ib_client.get_todays_executions()


def has_accurate_positions(accurate_positions: list) -> bool:
    return len(accurate_positions) > 0


def has_existing_positions() -> bool:
    return len(get_closed_positions()) > 0


def log_reconciliation_complete(count: int, logger: Logger):
    logger.info(f"Replaced {count} closed position(s) with accurate IBKR execution data")


def log_reconciliation_fallback(count: int, logger: Logger):
    logger.warning(f"Could not reconcile with IBKR - keeping {count} position(s) from state")


def log_reconciliation_footer(logger: Logger):
    logger.info("=" * 60)


def log_reconciliation_header(logger: Logger):
    logger.info("=" * 60)
    logger.info("RECONCILING CLOSED POSITIONS WITH IBKR EXECUTIONS")
    logger.info("=" * 60)


def reconcile_closed_positions_with_ibkr(s3_client, logger: Logger):
    log_reconciliation_header(logger)

    executions = get_ib_executions(logger)
    accurate_positions = generate_closed_positions_from_executions(executions, logger)

    if has_accurate_positions(accurate_positions):
        replace_positions_with_ibkr_data(accurate_positions)
        log_reconciliation_complete(len(accurate_positions), logger)
    elif has_existing_positions():
        log_reconciliation_fallback(len(get_closed_positions()), logger)

    log_reconciliation_footer(logger)


def replace_positions_with_ibkr_data(accurate_positions: list):
    from core.state import closed_positions_today
    closed_positions_today.clear()
    closed_positions_today.extend(accurate_positions)


def save_closed_positions_if_exist(s3_client, logger: Logger):
    from services.ibkr.ib_portfolio import save_closed_positions_to_s3

    if has_existing_positions():
        reconcile_closed_positions_with_ibkr(s3_client, logger)
        year, month, day = get_current_date()
        save_closed_positions_to_s3(year, month, day, s3_client, logger)


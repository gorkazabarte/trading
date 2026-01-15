"""
Connection management for IBKR Gateway.
"""
from logging import Logger
from time import sleep

from services.ibkr.ib_gateway_client import get_ib_client
from utils.time_utils import get_current_eastern_time, is_market_hours_now


def connect_to_ib_gateway(logger: Logger):
    logger.info("Connecting to IB Gateway for real-time market data...")
    log_market_status(logger)
    return establish_ib_connection(logger)


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


def log_market_status(logger: Logger):
    current_et_time = get_current_eastern_time()
    is_market_open = is_market_hours_now()
    logger.info(f"Current ET time: {current_et_time}")
    logger.info(f"Market status: {'OPEN' if is_market_open else 'CLOSED'}")


def wait_for_connection_establishment(logger: Logger):
    logger.info("Waiting 10 seconds for connection to fully establish...")
    sleep(10)
    logger.info("Connection ready. Proceeding with trading workflow.")


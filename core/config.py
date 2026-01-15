"""
Configuration and constants for the trading application.
"""
from datetime import time

MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 30
MARKET_CLOSE_HOUR = 16
MARKET_CLOSE_MINUTE = 0
MARKET_CLOSE_TIME = time(MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE)
MINUTES_BEFORE_CLOSE_TO_SELL = 15

S3_BUCKET = 'dev-trading-data-storage'
SETTINGS_FILE_PATH = 'files/settings.json'

IBKR_BASE_URL = "https://localhost:5001/v1/api/"

BUY_THRESHOLD_MULTIPLIER = 1.008

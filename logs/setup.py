"""Logging configuration for the trading application."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

MAX_LOG_FILE_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 5


def setup_logging(log_file: str = 'logs/app.log', log_level: int = logging.INFO) -> logging.Logger:
    """
    Setup logging configuration for the trading application.

    Args:
        log_file: Path to the log file
        log_level: Logging level

    Returns:
        Configured logger instance
    """
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(log_level)
    logger.handlers.clear()

    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=MAX_LOG_FILE_BYTES,
        backupCount=BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(detailed_formatter)
    logger.addHandler(console_handler)

    return logger

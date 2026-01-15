"""
File download operations from S3.
"""
from logging import Logger

from core.state import mark_files_as_downloaded
from utils.file_operations import download_companies_list, download_settings_file
from utils.time_utils import get_current_date


def are_files_downloaded(settings, companies) -> bool:
    return settings is not None and companies is not None


def download_daily_files(s3_client, bucket: str, year: int, month: int, day: int, logger: Logger):
    log_download_header(logger)

    settings, companies = download_files_from_s3(s3_client, bucket, year, month, day, logger)

    if are_files_downloaded(settings, companies):
        mark_downloads_complete(logger)
        log_download_footer(logger)
        return settings, companies

    logger.error("Failed to download one or more daily files")
    return None, None


def download_files_from_s3(s3_client, bucket: str, year: int, month: int, day: int, logger: Logger):
    settings = download_settings_file(s3_client, bucket, logger)
    companies = download_companies_list(s3_client, bucket, year, month, day, logger)
    return settings, companies


def download_required_files(s3_client, bucket: str, logger: Logger):
    year, month, day = get_current_date()
    settings, companies = download_daily_files(s3_client, bucket, year, month, day, logger)

    if not settings or not companies:
        logger.error("Failed to download required files. Application cannot start.")
        exit(1)

    return settings, companies


def log_download_footer(logger: Logger):
    logger.info("=" * 60)


def log_download_header(logger: Logger):
    logger.info("=" * 60)
    logger.info("DOWNLOADING DAILY FILES FROM S3")
    logger.info("=" * 60)


def mark_downloads_complete(logger: Logger):
    mark_files_as_downloaded()
    logger.info("Successfully downloaded all daily files")


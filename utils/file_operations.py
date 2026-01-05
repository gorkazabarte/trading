"""
File operations and S3 downloads.
"""
from typing import List, Dict, Optional
from os import makedirs, path
from json import loads
from logging import Logger


def is_cache_valid() -> bool:
    from core.state import is_files_downloaded
    return is_files_downloaded()


def build_local_file_path(year: int, month: int, day: int, filename: str) -> str:
    return f'./files/{year}/{month:02d}/{day:02d}/{filename}'


def build_s3_key(year: int, month: int, day: int, filename: str) -> str:
    return f'{year}/{month:02d}/{day:02d}/{filename}'


def ensure_directory_exists(file_path: str) -> None:
    makedirs(path.dirname(file_path), exist_ok=True)


def read_lines_from_file(file_path: str) -> List[str]:
    with open(file_path, 'r') as f:
        return f.read().splitlines()


def read_json_from_file(file_path: str) -> Dict:
    with open(file_path, 'r') as f:
        return loads(f.read())


def write_json_to_file(file_path: str, data: Dict) -> None:
    from json import dumps
    with open(file_path, 'w') as f:
        f.write(dumps(data, indent=2))


def download_file_from_s3(s3_client, bucket: str, s3_key: str, local_path: str) -> None:
    s3_client.download_file(bucket, s3_key, local_path)


def upload_file_to_s3(s3_client, bucket: str, local_path: str, s3_key: str) -> None:
    s3_client.upload_file(local_path, bucket, s3_key)


def download_companies_list(s3_client, bucket: str, year: int, month: int, day: int, logger: Logger) -> Optional[List[str]]:
    import core.state as state

    if is_cache_valid() and state.cached_companies is not None:
        logger.info(f"Using cached companies list ({len(state.cached_companies)} companies)")
        return state.cached_companies

    try:
        file_path = build_local_file_path(year, month, day, 'selected_companies.txt')
        ensure_directory_exists(file_path)

        s3_key = build_s3_key(year, month, day, 'selected_companies.txt')
        download_file_from_s3(s3_client, bucket, s3_key, file_path)

        state.cached_companies = read_lines_from_file(file_path)
        logger.info(f"Downloaded companies list from S3: {len(state.cached_companies)} companies")
        return state.cached_companies
    except Exception as e:
        logger.error(f"Companies were not selected for {year}/{month:02d}/{day:02d}. Error: {str(e)}")
        logger.error(f"Expected S3 location: s3://{bucket}/{year}/{month:02d}/{day:02d}/selected_companies.txt")
        return None


def download_settings_file(s3_client, bucket: str, logger: Logger) -> Optional[Dict]:
    import core.state as state

    if is_cache_valid() and state.cached_settings is not None:
        logger.info("Using cached settings.json")
        return state.cached_settings

    try:
        makedirs('./files', exist_ok=True)
        download_file_from_s3(s3_client, bucket, 'settings.json', './files/settings.json')

        state.cached_settings = read_json_from_file('./files/settings.json')
        logger.info("Downloaded settings.json from S3")
        return state.cached_settings
    except Exception as e:
        logger.error(f"Failed to download settings.json: {str(e)}")
        return None


def create_directories(year: int, month: int, day: int) -> str:
    market_data_dir = f'./files/{year}/{month:02d}/{day:02d}'
    makedirs(market_data_dir, exist_ok=True)
    makedirs('./files', exist_ok=True)
    return market_data_dir

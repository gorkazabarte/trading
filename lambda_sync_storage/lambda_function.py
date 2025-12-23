import json
import logging
from os import environ
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from boto3 import client
import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = client("s3")

CSV_FILENAME = "all_companies.csv"
ENV_DRIVE_FOLDER_URL = "DRIVE_FOLDER_URL"
ENV_S3_BUCKET = "S3_BUCKET_NAME"
EXPORT_MIME_TYPE_CSV = "text/csv"
MONTHS_AHEAD = 2


def build_s3_key(year: int, month: int, day: int) -> str:
    return f"{year}/{month}/{day}/{CSV_FILENAME}"


def create_error_response(status_code: int, message: str) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "body": json.dumps({"error": message})
    }


def create_success_response(processed_dates: List[str], skipped: int) -> Dict[str, Any]:
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": f"Successfully processed {len(processed_dates)} date(s), skipped {skipped}",
            "dates": processed_dates
        })
    }


def download_csv_from_url(url: str) -> Optional[str]:
    try:
        logger.info(f"Downloading CSV from URL")
        session = requests.Session()
        response = session.get(url, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Failed to download from URL: {str(e)}")
        return None


def extract_file_id_from_url(url: str) -> Optional[str]:
    """
    Extract file ID from Google Drive URL.
    Supports formats:
    - https://drive.google.com/file/d/FILE_ID/view
    - https://drive.google.com/open?id=FILE_ID
    - https://drive.google.com/uc?id=FILE_ID
    """
    try:
        if '/file/d/' in url:
            file_id = url.split('/file/d/')[1].split('/')[0]
        elif 'id=' in url:
            file_id = url.split('id=')[1].split('&')[0]
        else:
            logger.error(f"Unsupported URL format: {url}")
            return None
        return file_id
    except Exception as e:
        logger.error(f"Error extracting file ID from URL: {str(e)}")
        return None


def generate_date_range(start_date: datetime, months: int) -> List[tuple[int, int, int]]:
    dates = []
    current_date = start_date
    end_date = start_date + timedelta(days=30 * months)

    while current_date <= end_date:
        dates.append((current_date.year, current_date.month, current_date.day))
        current_date += timedelta(days=1)

    return dates


def get_drive_folder_url() -> str:
    return environ[ENV_DRIVE_FOLDER_URL]


def get_s3_bucket() -> str:
    return environ[ENV_S3_BUCKET]


def get_start_date() -> datetime:
    return datetime.now()


def process_single_date(s3_bucket: str, drive_folder_url: str, year: int, month: int, day: int) -> bool:
    try:
        logger.info(f"Processing {year}/{month:02d}/{day:02d}")

        file_id = extract_file_id_from_url(drive_folder_url)
        if not file_id:
            logger.warning(f"Skipping {year}/{month:02d}/{day:02d} - invalid Google Drive URL")
            return False

        download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        csv_content = download_csv_from_url(download_url)

        if not csv_content:
            logger.warning(f"Skipping {year}/{month:02d}/{day:02d} - failed to download")
            return False

        s3_key = build_s3_key(year, month, day)
        upload_to_s3(csv_content, s3_bucket, s3_key)

        logger.info(f"Successfully uploaded to s3://{s3_bucket}/{s3_key}")
        return True

    except Exception as e:
        logger.error(f"Error processing {year}/{month:02d}/{day:02d}: {str(e)}")
        return False


def upload_to_s3(content: str, bucket: str, key: str) -> None:
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=content.encode('utf-8'),
        ContentType=EXPORT_MIME_TYPE_CSV
    )


def lambda_handler(event, context):
    try:
        logger.info("Starting CSV sync from Google Drive to S3")

        drive_folder_url = get_drive_folder_url()
        s3_bucket = get_s3_bucket()
        start_date = get_start_date()

        date_range = generate_date_range(start_date, MONTHS_AHEAD)
        logger.info(f"Processing {len(date_range)} dates (today + {MONTHS_AHEAD} months)")
        logger.info(f"Using Google Drive URL: {drive_folder_url}")

        processed_dates = []
        skipped = 0

        for year, month, day in date_range:
            success = process_single_date(s3_bucket, drive_folder_url, year, month, day)
            if success:
                processed_dates.append(f"{year}-{month:02d}-{day:02d}")
            else:
                skipped += 1

        logger.info(f"Completed: {len(processed_dates)}/{len(date_range)} files uploaded, {skipped} skipped")
        return create_success_response(processed_dates, skipped)

    except KeyError as e:
        logger.error(f"Missing environment variable: {e}")
        return create_error_response(500, f"Configuration error: Missing {e}")

    except Exception as e:
        logger.error(f"Error processing files: {str(e)}", exc_info=True)
        return create_error_response(500, f"Failed to process files: {str(e)}")


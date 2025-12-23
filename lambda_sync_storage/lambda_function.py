import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from boto3 import client
from google.oauth2 import service_account
from googleapiclient.discovery import build
import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = client("s3")
secrets_client = client("secretsmanager")

CSV_FILENAME = "all_companies.csv"
DRIVE_API_VERSION = "v3"
DRIVE_FOLDER_PREFIX = "trading"
ENV_SECRET_NAME = "GOOGLE_SERVICE_ACCOUNT_SECRET_NAME"
ENV_S3_BUCKET = "S3_BUCKET_NAME"
EXPORT_MIME_TYPE_CSV = "text/csv"
MONTHS_AHEAD = 2
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

drive_service = None


def build_drive_download_url(file_id: str) -> str:
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def build_drive_path(year: int, month: int, day: int) -> str:
    return f"{DRIVE_FOLDER_PREFIX}/{year}/{month}/{day}"


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


def find_file_in_folder(folder_path: str, filename: str) -> Optional[str]:
    try:
        folder_parts = folder_path.split("/")
        folder_id = find_folder_by_path(folder_parts)

        if not folder_id:
            logger.warning(f"Folder not found: {folder_path}")
            return None

        query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
        results = drive_service.files().list(
            q=query,
            fields="files(id, name)",
            pageSize=1
        ).execute()

        files = results.get('files', [])
        if files:
            return files[0]['id']

        logger.warning(f"File '{filename}' not found in folder: {folder_path}")
        return None

    except Exception as e:
        logger.error(f"Error finding file in folder {folder_path}: {str(e)}")
        return None


def find_folder_by_path(folder_parts: List[str]) -> Optional[str]:
    current_parent = 'root'

    for folder_name in folder_parts:
        query = f"name='{folder_name}' and '{current_parent}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = drive_service.files().list(
            q=query,
            fields="files(id, name)",
            pageSize=1
        ).execute()

        folders = results.get('files', [])
        if not folders:
            return None

        current_parent = folders[0]['id']

    return current_parent


def get_drive_service():
    global drive_service
    if drive_service is None:
        credentials = get_credentials_from_env()
        drive_service = build("drive", DRIVE_API_VERSION, credentials=credentials)
    return drive_service


def get_credentials_from_env() -> service_account.Credentials:
    secret_name = os.environ.get(ENV_SECRET_NAME, "google-service-account-trading")
    service_account_json = get_secret(secret_name)
    service_account_info = json.loads(service_account_json)

    return service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES
    )


def get_secret(secret_name: str) -> str:
    try:
        logger.info(f"Retrieving secret: {secret_name}")
        response = secrets_client.get_secret_value(SecretId=secret_name)

        if 'SecretString' in response:
            return response['SecretString']
        else:
            logger.error(f"Secret {secret_name} does not contain SecretString")
            raise ValueError(f"Secret {secret_name} is not a string secret")

    except Exception as e:
        logger.error(f"Error retrieving secret {secret_name}: {str(e)}")
        raise


def download_from_google_drive(file_id: str) -> Optional[str]:
    try:
        url = build_drive_download_url(file_id)

        session = requests.Session()
        response = session.get(url, timeout=30)

        # Handle large files confirmation
        if 'download_warning' in response.text or 'virus scan warning' in response.text:
            for key, value in response.cookies.items():
                if key.startswith('download_warning'):
                    token = value
                    break
            else:
                token = 'confirm'

            url_with_confirm = f"{url}&confirm={token}"
            response = session.get(url_with_confirm, timeout=30)

        response.raise_for_status()
        return response.text

    except requests.RequestException as e:
        logger.error(f"Failed to download from Google Drive (file_id: {file_id}): {str(e)}")
        return None


def generate_date_range(start_date: datetime, months: int) -> List[tuple[int, int, int]]:
    dates = []
    current_date = start_date
    end_date = start_date + timedelta(days=30 * months)

    while current_date <= end_date:
        dates.append((current_date.year, current_date.month, current_date.day))
        current_date += timedelta(days=1)

    return dates


def get_drive_file_id_for_date(year: int, month: int, day: int) -> Optional[str]:
    """
    Get Google Drive file ID for a specific date.

    Store your file IDs in Lambda environment variable as JSON:
    FILE_ID_MAPPING = {
        "2025-12-23": "1ABC123...",
        "2025-12-24": "1XYZ789...",
        ...
    }
    """
    try:
        file_mapping = json.loads(os.environ.get('FILE_ID_MAPPING', '{}'))
        date_key = f"{year}-{month:02d}-{day:02d}"
        return file_mapping.get(date_key)
    except Exception as e:
        logger.error(f"Error loading file ID mapping: {str(e)}")
        return None


def get_s3_bucket() -> str:
    return os.environ[ENV_S3_BUCKET]


def get_start_date() -> datetime:
    return datetime.now()


def process_single_date(s3_bucket: str, year: int, month: int, day: int) -> bool:
    try:
        logger.info(f"Processing {year}/{month:02d}/{day:02d}")

        drive_path = build_drive_path(year, month, day)
        file_id = find_file_in_folder(drive_path, CSV_FILENAME)

        if not file_id:
            logger.warning(f"Skipping {year}/{month:02d}/{day:02d} - file not found at path: {drive_path}")
            return False

        csv_content = download_from_google_drive(file_id)

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

        get_drive_service()
        s3_bucket = get_s3_bucket()
        start_date = get_start_date()

        date_range = generate_date_range(start_date, MONTHS_AHEAD)
        logger.info(f"Processing {len(date_range)} dates (today + {MONTHS_AHEAD} months)")

        processed_dates = []
        skipped = 0

        for year, month, day in date_range:
            success = process_single_date(s3_bucket, year, month, day)
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


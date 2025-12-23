import json
from os import environ
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from boto3 import client
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io


s3_client = client("s3")
secrets_client = client("secretsmanager")

CSV_FILENAME = "all_companies.csv"
DRIVE_API_VERSION = "v3"
DRIVE_FOLDER_PREFIX = "trading"
ENV_SECRET_NAME = "SVC_ACCOUNT_SECRET_NAME"
ENV_S3_BUCKET = "S3_BUCKET"
EXPORT_MIME_TYPE_CSV = "text/csv"
MONTHS_AHEAD = 2
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

drive_service = None


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


def download_file_from_drive(file_id: str) -> Optional[str]:
    try:
        request = drive_service.files().get_media(fileId=file_id)

        file_buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(file_buffer, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()

        file_buffer.seek(0)
        return file_buffer.read().decode('utf-8')

    except Exception as e:
        return None


def find_file_in_folder(folder_path: str, filename: str) -> Optional[str]:
    try:
        folder_parts = folder_path.split("/")
        folder_id = find_folder_by_path(folder_parts)

        if not folder_id:
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

        return None

    except Exception as e:
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


def generate_date_range(start_date: datetime, months: int) -> List[tuple[int, int, int]]:
    dates = []
    current_date = start_date
    end_date = start_date + timedelta(days=30 * months)

    while current_date <= end_date:
        dates.append((current_date.year, current_date.month, current_date.day))
        current_date += timedelta(days=1)

    return dates


def get_credentials_from_secrets_manager() -> service_account.Credentials:
    secret_name = environ.get(ENV_SECRET_NAME, "dev-trading-service-account")
    service_account_json = get_secret(secret_name)
    service_account_info = json.loads(service_account_json)

    return service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES
    )


def get_drive_service():
    global drive_service
    if drive_service is None:
        credentials = get_credentials_from_secrets_manager()
        drive_service = build("drive", DRIVE_API_VERSION, credentials=credentials)
    return drive_service


def get_secret(secret_name: str) -> str:
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)

        if 'SecretString' in response:
            return response['SecretString']
        else:
            print(f"ERROR: Secret {secret_name} is not a string secret")
            raise ValueError(f"Secret {secret_name} is not a string secret")

    except Exception as e:
        print(f"ERROR: Failed to retrieve secret {secret_name}: {str(e)}")
        raise


def get_s3_bucket() -> str:
    bucket = environ.get(ENV_S3_BUCKET)
    if not bucket:
        raise ValueError(f"Environment variable {ENV_S3_BUCKET} is not set")
    return bucket


def get_start_date() -> datetime:
    return datetime.now()


def process_single_date(s3_bucket: str, year: int, month: int, day: int) -> bool:
    try:
        drive_path = build_drive_path(year, month, day)
        file_id = find_file_in_folder(drive_path, CSV_FILENAME)

        if not file_id:
            return False

        csv_content = download_file_from_drive(file_id)

        if not csv_content:
            return False

        s3_key = build_s3_key(year, month, day)
        upload_to_s3(csv_content, s3_bucket, s3_key)

        return True

    except Exception as e:
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
        get_drive_service()
        s3_bucket = get_s3_bucket()
        start_date = get_start_date()
        date_range = generate_date_range(start_date, MONTHS_AHEAD)

        processed_dates = []
        skipped = 0

        for year, month, day in date_range:
            success = process_single_date(s3_bucket, year, month, day)
            if success:
                processed_dates.append(f"{year}-{month:02d}-{day:02d}")
            else:
                skipped += 1

        return create_success_response(processed_dates, skipped)

    except KeyError as e:
        return create_error_response(500, f"Configuration error: Missing environment variable {e}")

    except Exception as e:
        return create_error_response(500, f"Failed to process files: {str(e)}")


from io import BytesIO
from json import dumps, loads
from datetime import datetime, timedelta
from os import environ
from typing import Any, Dict, List, Optional

from boto3 import client
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

CSV_FILENAME = "all_companies.csv"
DRIVE_API_VERSION = "v3"
DRIVE_FOLDER_PREFIX = "trading"
ENV_S3_BUCKET = "S3_BUCKET"
ENV_SECRET_NAME = "SVC_ACCOUNT_SECRET_NAME"
EXPORT_MIME_TYPE_CSV = "text/csv"
MONTHS_AHEAD = 2
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

drive_service = None
s3_client = client("s3")
secrets_client = client("secretsmanager")


def build_csv_filename_for_s3(year: int, month: int, day: int) -> str:
    return f"{year}/{month:02d}/{day:02d}/{CSV_FILENAME}"


def build_drive_folder_path(year: int, month: int, day: int) -> str:
    return f"{DRIVE_FOLDER_PREFIX}/{year}/{month:02d}/{day:02d}"


def create_date_range_for_next_months(start_date: datetime, months: int) -> List[tuple]:
    dates = []
    current_date = start_date
    end_date = start_date + timedelta(days=30 * months)

    while current_date <= end_date:
        dates.append((current_date.year, current_date.month, current_date.day))
        current_date += timedelta(days=1)

    return dates


def create_error_response_with_message(status_code: int, message: str) -> Dict[str, Any]:
    return create_lambda_response(status_code, {"error": message})


def create_lambda_response(status_code: int, body_content: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "body": dumps(body_content)
    }


def create_success_response_with_dates(processed_dates: List[str], skipped_count: int) -> Dict[str, Any]:
    message = f"Successfully processed {len(processed_dates)} date(s), skipped {skipped_count}"
    body_content = {
        "message": message,
        "dates": processed_dates
    }
    return create_lambda_response(200, body_content)


def decode_downloaded_file_content(file_buffer: BytesIO) -> str:
    file_buffer.seek(0)
    return file_buffer.read().decode('utf-8')


def download_file_content_from_drive(file_id: str) -> Optional[str]:
    try:
        file_buffer = download_file_to_buffer(file_id)
        return decode_downloaded_file_content(file_buffer)
    except Exception:
        return None


def download_file_to_buffer(file_id: str) -> BytesIO:
    request = drive_service.files().get_media(fileId=file_id)
    file_buffer = BytesIO()
    downloader = MediaIoBaseDownload(file_buffer, request)

    download_complete = False
    while not download_complete:
        _, download_complete = downloader.next_chunk()

    return file_buffer



def execute_drive_query_for_files(query: str) -> List[Dict]:
    results = drive_service.files().list(
        q=query,
        fields="files(id, name)",
        pageSize=1,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()
    return results.get('files', [])


def find_file_by_name_in_folder(filename: str, folder_id: str) -> Optional[str]:
    query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
    files = execute_drive_query_for_files(query)

    if files:
        print(f"Found file '{filename}' with ID: {files[0]['id']}")
        return files[0]['id']

    print(f"ERROR: File '{filename}' not found")
    return None


def find_file_id_in_drive_folder_path(folder_path: str, filename: str) -> Optional[str]:
    try:
        folder_parts = folder_path.split("/")
        print(f"Finding folder by path parts: {folder_parts}")

        folder_id = find_folder_id_by_path_parts(folder_parts)
        print(f"Found folder ID: {folder_id}")

        if not folder_id:
            print(f"ERROR: Folder not found: {folder_path}")
            return None

        return find_file_by_name_in_folder(filename, folder_id)
    except Exception as e:
        print(f"ERROR: Exception in find_file_id_in_drive_folder_path: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def execute_drive_query_for_folders(query: str, page_size: int = 1) -> List[Dict]:
    results = drive_service.files().list(
        q=query,
        fields="files(id, name, parents)",
        pageSize=page_size,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()
    return results.get('files', [])


def find_first_folder_globally(folder_name: str) -> Optional[str]:
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    folders = execute_drive_query_for_folders(query, page_size=5)

    if not folders:
        return None

    if len(folders) > 1:
        print(f"Found {len(folders)} folders named '{folder_name}', using first one")
    else:
        print(f"Found folder '{folder_name}' with ID: {folders[0]['id']}")

    return folders[0]['id']


def find_folder_id_by_path_parts(folder_parts: List[str]) -> Optional[str]:
    current_parent_id = None

    for index, folder_name in enumerate(folder_parts):
        if is_first_folder(index):
            current_parent_id = find_first_folder_globally(folder_name)
        else:
            current_parent_id = find_subfolder_under_parent(folder_name, current_parent_id)

        if not current_parent_id:
            return None

    return current_parent_id


def find_subfolder_under_parent(folder_name: str, parent_id: str) -> Optional[str]:
    print(f"Searching for folder '{folder_name}' under parent '{parent_id}'")
    query = f"name='{folder_name}' and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    folders = execute_drive_query_for_folders(query)

    if not folders:
        print(f"ERROR: Folder '{folder_name}' not found under parent '{parent_id}'")
        return None

    print(f"Using folder ID: {folders[0]['id']}")
    return folders[0]['id']


def is_first_folder(index: int) -> bool:
    return index == 0


def get_credentials_from_secrets_manager() -> service_account.Credentials:
    secret_name = get_secret_name_from_environment()
    service_account_json = get_secret_value(secret_name)
    service_account_info = loads(service_account_json)

    return service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES
    )


def get_drive_service():
    global drive_service
    if drive_service is None:
        credentials = get_credentials_from_secrets_manager()
        drive_service = build("drive", DRIVE_API_VERSION, credentials=credentials)
        log_accessible_folders()
    return drive_service


def get_s3_bucket_name() -> str:
    bucket = environ.get(ENV_S3_BUCKET)
    if not bucket:
        raise ValueError(f"Environment variable {ENV_S3_BUCKET} is not set")
    return bucket


def get_secret_name_from_environment() -> str:
    return environ.get(ENV_SECRET_NAME, "dev-trading-service-account")


def get_secret_value(secret_name: str) -> str:
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


def get_start_date() -> datetime:
    return datetime.now()


def log_accessible_folders():
    try:
        print("Listing all accessible folders...")
        folders = query_all_accessible_folders()
        print(f"Service account can see {len(folders)} folders:")
        for folder in folders:
            parents = folder.get('parents', ['<no parent>'])
            print(f"  - {folder['name']} (ID: {folder['id']}, Parents: {parents})")
    except Exception as e:
        print(f"WARNING: Could not list folders: {str(e)}")


def process_csv_file_for_date(s3_bucket: str, year: int, month: int, day: int) -> bool:
    try:
        print(f"Processing date: {year}-{month:02d}-{day:02d}")

        file_content = retrieve_csv_from_drive(year, month, day)
        if not file_content:
            return False

        upload_csv_to_s3(file_content, s3_bucket, year, month, day)
        return True
    except Exception:
        return False


def query_all_accessible_folders() -> List[Dict]:
    results = drive_service.files().list(
        q="mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id, name, parents)",
        pageSize=50,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()
    return results.get('files', [])


def retrieve_csv_from_drive(year: int, month: int, day: int) -> Optional[str]:
    drive_path = build_drive_folder_path(year, month, day)
    print(f"Looking for file in Drive path: {drive_path}")

    file_id = find_file_id_in_drive_folder_path(drive_path, CSV_FILENAME)
    print(f"Found file ID: {file_id}")

    if not file_id:
        return None

    return download_file_content_from_drive(file_id)


def upload_csv_to_s3(content: str, bucket: str, year: int, month: int, day: int) -> None:
    s3_key = build_csv_filename_for_s3(year, month, day)
    s3_client.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=content.encode('utf-8'),
        ContentType=EXPORT_MIME_TYPE_CSV
    )


def lambda_handler(event, context):
    try:
        initialize_services()
        processed_dates, skipped_count = process_all_dates()
        return create_success_response_with_dates(processed_dates, skipped_count)
    except KeyError as e:
        return create_error_response_with_message(500, f"Configuration error: Missing environment variable {e}")
    except Exception as e:
        return create_error_response_with_message(500, f"Failed to process files: {str(e)}")


def initialize_services():
    get_drive_service()


def process_all_dates() -> tuple:
    s3_bucket = get_s3_bucket_name()
    date_range = create_date_range_for_next_months(get_start_date(), MONTHS_AHEAD)

    processed_dates = []
    skipped_count = 0

    for year, month, day in date_range:
        if process_csv_file_for_date(s3_bucket, year, month, day):
            processed_dates.append(f"{year}-{month:02d}-{day:02d}")
        else:
            skipped_count += 1

    return processed_dates, skipped_count




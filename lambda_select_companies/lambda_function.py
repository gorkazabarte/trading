from boto3 import client
from datetime import datetime, timezone
from json import dumps, loads
from os import environ

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS, GET",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With"
}

S3_BUCKET = environ.get('S3_BUCKET')

s3 = client('s3')


def create_companies_txt_content(companies: list) -> str:
    return '\n'.join(str(ticker).strip() for ticker in companies if ticker)


def create_response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "body": dumps(body),
        "headers": CORS_HEADERS
    }


def create_s3_key(year: int, month: int, day: int) -> str:
    return f"{year}/{month:02}/{day:02}/selected_companies.txt"


def create_timestamp() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y%m%d_%H%M%S")


def handle_options_request():
    return {
        "statusCode": 200,
        "headers": CORS_HEADERS
    }


def is_valid_day(day: int) -> bool:
    return 1 <= day <= 31


def is_valid_month(month: int) -> bool:
    return 1 <= month <= 12


def lambda_handler(event, context):
    if event.get('httpMethod') == 'OPTIONS':
        return handle_options_request()

    try:
        body = parse_request_body(event)

        is_valid, error_message = validate_required_fields(body)
        if not is_valid:
            return create_response(400, {"error": error_message})

        success, date_tuple, error_message = parse_date_fields(body)
        if not success:
            return create_response(400, {"error": error_message})

        year, month, day = date_tuple

        is_valid, error_message = validate_date_ranges(year, month, day)
        if not is_valid:
            return create_response(400, {"error": error_message})

        companies = body['companies']

        is_valid, error_message = validate_companies_list(companies)
        if not is_valid:
            return create_response(400, {"error": error_message})

        txt_content = create_companies_txt_content(companies)
        s3_key = create_s3_key(year, month, day)

        upload_to_s3(s3_key, txt_content)

        return create_response(200, {
            "message": "Companies list uploaded successfully",
            "s3_bucket": S3_BUCKET,
            "s3_key": s3_key,
            "companies_count": len(companies),
            "timestamp": create_timestamp()
        })

    except Exception as e:
        return create_response(500, {
            "error": "Internal server error",
            "message": str(e)
        })


def parse_date_fields(body: dict) -> tuple[bool, tuple, str]:
    try:
        year = int(body['year'])
        month = int(body['month'])
        day = int(body['day'])
        return True, (year, month, day), ""
    except (ValueError, TypeError):
        return False, None, "year, month, and day must be valid integers"


def parse_request_body(event: dict) -> dict:
    if 'body' in event:
        if isinstance(event['body'], str):
            return loads(event['body'])
        return event['body']
    return event


def upload_to_s3(s3_key: str, content: str) -> None:
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=content.encode('utf-8'),
        ContentType='text/plain'
    )


def validate_companies_list(companies) -> tuple[bool, str]:
    if not isinstance(companies, list):
        return False, "'companies' must be an array"

    if len(companies) == 0:
        return False, "'companies' array cannot be empty"

    return True, ""


def validate_date_ranges(year: int, month: int, day: int) -> tuple[bool, str]:
    if not is_valid_month(month):
        return False, "month must be between 1 and 12"

    if not is_valid_day(day):
        return False, "day must be between 1 and 31"

    try:
        datetime(year, month, day)
        return True, ""
    except ValueError as e:
        return False, f"Invalid date: {str(e)}"


def validate_required_fields(body: dict) -> tuple[bool, str]:
    if not body:
        return False, "Request body is empty"

    required_fields = ['companies', 'year', 'month', 'day']
    missing_fields = [field for field in required_fields if field not in body]

    if missing_fields:
        return False, f"Missing required field(s): {', '.join(missing_fields)}"

    return True, ""



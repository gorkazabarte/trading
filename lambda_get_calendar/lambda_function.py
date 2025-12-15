from boto3 import client
from json import JSONDecodeError, dumps, loads
from os import environ

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*"
}

S3_BUCKET = environ.get("S3_BUCKET")

s3 = client("s3")


def build_s3_key(year: int, month: int) -> str:
    return f"{year}/{month:02d}/filtered_companies.json"


def create_response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "body": dumps(body),
        "headers": CORS_HEADERS
    }


def extract_path_parameters(event: dict) -> tuple[str, str]:
    path_params = event.get("pathParameters", {})
    year = path_params.get("year")
    month = path_params.get("month")
    return year, month


def fetch_calendar_data_from_s3(key: str) -> str:
    response = s3.get_object(Bucket=S3_BUCKET, Key=key)
    return response["Body"].read().decode("utf-8")


def is_valid_month(month: int) -> bool:
    return 1 <= month <= 12


def lambda_handler(event, context):
    year, month = extract_path_parameters(event)

    if not year or not month:
        return create_response(400, {"error": "Missing year or month parameters"})

    is_valid, year_int, month_int, error_message = parse_and_validate_dates(year, month)
    if not is_valid:
        return create_response(400, {"error": error_message})

    key = build_s3_key(year_int, month_int)

    try:
        data = fetch_calendar_data_from_s3(key)
        validate_json_format(data)

        return {
            "statusCode": 200,
            "body": data,
            "headers": CORS_HEADERS
        }

    except s3.exceptions.NoSuchKey:
        return create_response(404, {
            "error": "Calendar data not found",
            "message": f"No data available for {year}/{month:02d}"
        })

    except s3.exceptions.NoSuchBucket:
        return create_response(500, {"error": "Configuration error: S3 bucket not found"})

    except JSONDecodeError:
        return create_response(500, {"error": "Data format error"})

    except Exception:
        return create_response(500, {"error": "Internal server error"})


def parse_and_validate_dates(year: str, month: str) -> tuple[bool, int, int, str]:
    try:
        year_int = int(year)
        month_int = int(month)

        if not is_valid_month(month_int):
            return False, 0, 0, "Month must be between 1 and 12"

        return True, year_int, month_int, ""

    except ValueError as e:
        return False, 0, 0, f"Invalid year or month format: {str(e)}"


def validate_json_format(data: str) -> None:
    loads(data)

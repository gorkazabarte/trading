from boto3 import client
from json import JSONDecodeError, dumps, loads
from os import environ

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS, GET",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With"
}

REQUIRED_SETTINGS = ['stopLoss', 'takeProfit', 'nextInvestment', 'opsPerDay']

S3_BUCKET = environ.get('S3_BUCKET')
S3_KEY = environ.get('S3_KEY', 'settings.json')

s3 = client('s3')


def create_response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "body": dumps(body),
        "headers": CORS_HEADERS
    }


def create_s3_location() -> str:
    return f"s3://{S3_BUCKET}/{S3_KEY}"


def extract_settings(body: dict) -> dict:
    return {setting: body[setting] for setting in REQUIRED_SETTINGS}


def handle_options_request():
    return {"statusCode": 200, "headers": CORS_HEADERS}


def lambda_handler(event, context):
    if event.get('httpMethod') == 'OPTIONS':
        return handle_options_request()

    try:
        body = parse_request_body(event)

        is_valid, error_message = validate_request_body(body)
        if not is_valid:
            return create_response(400, {"error": error_message})

        settings = extract_settings(body)
        upload_settings_to_s3(settings)

        return create_response(200, {
            "message": "Settings updated successfully",
            "updatedSettings": settings,
            "s3_location": create_s3_location()
        })

    except JSONDecodeError:
        return create_response(400, {"error": "Invalid JSON format"})

    except s3.exceptions.NoSuchBucket:
        return create_response(500, {"error": f"Configuration error: S3 bucket '{S3_BUCKET}' not found"})

    except Exception as e:
        return create_response(500, {"error": f"Internal server error: {str(e)}"})


def parse_request_body(event: dict) -> dict:
    if 'body' in event:
        if isinstance(event['body'], str):
            return loads(event['body'])
        return event['body']
    return event


def upload_settings_to_s3(settings: dict) -> None:
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=S3_KEY,
        Body=dumps(settings, indent=2),
        ContentType='application/json'
    )


def validate_request_body(body: dict) -> tuple[bool, str]:
    if not body:
        return False, "Request body is empty"

    missing_fields = [field for field in REQUIRED_SETTINGS if field not in body]
    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"

    return True, ""


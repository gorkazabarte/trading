from boto3 import client
from json import dumps, loads
from os import environ
from datetime import datetime, timezone

s3 = client('s3')
S3_BUCKET = environ.get('S3_BUCKET')


def lambda_handler(event, context):
    """
    AWS Lambda handler for creating a txt file in S3 with selected companies.
    Expects a JSON body with a 'companies' array containing ticker symbols.
    Creates a txt file with one ticker per line in S3.
    """

    if event.get('httpMethod') == 'OPTIONS':
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS, GET",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        }

    try:
        if 'body' in event:
            if isinstance(event['body'], str):
                body = loads(event['body'])
            else:
                body = event['body']
        else:
            body = event

        if not body:
            return {
                "statusCode": 400,
                "body": dumps({"error": "Request body is empty"}),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS, GET",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With"
                }
            }

        required_fields = ['companies', 'year', 'month', 'day']
        missing_fields = [field for field in required_fields if field not in body]

        if missing_fields:
            return {
                "statusCode": 400,
                "body": dumps({"error": f"Missing required field(s): {', '.join(missing_fields)}"}),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS, GET",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With"
                }
            }

        companies = body['companies']
        year = body['year']
        month = body['month']
        day = body['day']

        try:
            year = int(year)
            month = int(month)
            day = int(day)
        except (ValueError, TypeError):
            return {
                "statusCode": 400,
                "body": dumps({"error": "year, month, and day must be valid integers"}),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS, GET",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With"
                }
            }

        if not (1 <= month <= 12):
            return {
                "statusCode": 400,
                "body": dumps({"error": "month must be between 1 and 12"}),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS, GET",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With"
                }
            }

        if not (1 <= day <= 31):
            return {
                "statusCode": 400,
                "body": dumps({"error": "day must be between 1 and 31"}),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS, GET",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With"
                }
            }

        try:
            datetime(year, month, day)
        except ValueError as e:
            return {
                "statusCode": 400,
                "body": dumps({"error": f"Invalid date: {str(e)}"}),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS, GET",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With"
                }
            }

        if not isinstance(companies, list):
            return {
                "statusCode": 400,
                "body": dumps({"error": "'companies' must be an array"}),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS, GET",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With"
                }
            }

        if len(companies) == 0:
            return {
                "statusCode": 400,
                "body": dumps({"error": "'companies' array cannot be empty"}),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS, GET",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With"
                }
            }

        txt_content = '\n'.join(str(ticker).strip() for ticker in companies if ticker)

        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        s3_key = f"{year}/{month:02}/{day:02}/selected_companies.txt"

        s3.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=txt_content.encode('utf-8'),
            ContentType='text/plain'
        )


        return {
            "statusCode": 200,
            "body": dumps({
                "message": "Companies list uploaded successfully",
                "s3_bucket": S3_BUCKET,
                "s3_key": s3_key,
                "companies_count": len(companies),
                "timestamp": timestamp
            }),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS, GET",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With"
            }
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": dumps({
                "error": "Internal server error",
                "message": str(e)
            }),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS, GET",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With"
            }
        }


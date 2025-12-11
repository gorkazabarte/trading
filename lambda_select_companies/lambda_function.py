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

    print(f"Received event: {event}")

    # Handle CORS preflight request
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
        # Parse the request body
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

        # Validate required field
        if 'companies' not in body:
            return {
                "statusCode": 400,
                "body": dumps({"error": "Missing required field: 'companies'"}),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS, GET",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With"
                }
            }

        companies = body['companies']

        # Validate that companies is a list
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

        # Validate that companies list is not empty
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
        year = now.year
        month = now.month
        s3_key = f"{year}/{month:02}/selected_companies_{timestamp}.txt"

        s3.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=txt_content.encode('utf-8'),
            ContentType='text/plain'
        )

        print(f"Successfully uploaded {len(companies)} companies to s3://{S3_BUCKET}/{s3_key}")

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
        print(f"Error: {str(e)}")
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


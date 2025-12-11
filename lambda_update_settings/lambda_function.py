from boto3 import client
from json import JSONDecodeError, loads, dumps
from os import environ

s3 = client('s3')
S3_BUCKET = environ.get('S3_BUCKET')
S3_KEY = environ.get('S3_KEY', 'settings.json')


def lambda_handler(event, context):
    """
    AWS Lambda handler for updating settings in S3.
    Expects a JSON body with stopLoss, takeProfit, nextInvestment, and opsPerDay values.
    Settings are stored as a JSON object in S3.
    """

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

        required_settings = ['stopLoss', 'takeProfit', 'nextInvestment', 'opsPerDay']

        missing_fields = [field for field in required_settings if field not in body]
        if missing_fields:
            return {
                "statusCode": 400,
                "body": dumps({"error": f"Missing required fields: {', '.join(missing_fields)}"}),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS, GET",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With"
                }
            }

        settings = {
            setting_name: body[setting_name]
            for setting_name in required_settings
        }

        s3.put_object(
            Bucket=S3_BUCKET,
            Key=S3_KEY,
            Body=dumps(settings, indent=2),
            ContentType='application/json'
        )

        return {
            "statusCode": 200,
            "body": dumps({
                "message": "Settings updated successfully",
                "updatedSettings": settings,
                "s3_location": f"s3://{S3_BUCKET}/{S3_KEY}"
            }),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS, GET",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With"
            }
        }

    except JSONDecodeError as e:
        return {
            "statusCode": 400,
            "body": dumps({"error": "Invalid JSON format"}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS, GET",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With"
            }
        }
    except s3.exceptions.NoSuchBucket:
        return {
            "statusCode": 500,
            "body": dumps({"error": f"Configuration error: S3 bucket '{S3_BUCKET}' not found"}),
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
            "body": dumps({"error": f"Internal server error: {str(e)}"}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS, GET",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With"
            }
        }

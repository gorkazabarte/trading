from boto3 import client
from json import dumps, loads, JSONDecodeError
import os

S3_BUCKET = os.environ.get("S3_BUCKET")
s3 = client("s3")


def lambda_handler(event, context):
    """
    AWS Lambda handler for API Gateway endpoint: /calendar/{year}/{month}
    Retrieves filtered companies data from S3 bucket for the specified year and month.
    """

    path_params = event.get("pathParameters", {})
    year = path_params.get("year")
    month = path_params.get("month")

    if not year or not month:
        return {
            "statusCode": 400,
            "body": dumps({"error": "Missing year or month parameters"}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }

    try:
        year_int = int(year)
        month_int = int(month)

        if month_int < 1 or month_int > 12:
            raise ValueError("Month must be between 1 and 12")

    except ValueError as e:
        return {
            "statusCode": 400,
            "body": dumps({"error": f"Invalid year or month format: {str(e)}"}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }

    key = f"{year_int}/{month_int:02d}/filtered_companies.json"

    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key=key)
        data = response["Body"].read().decode("utf-8")

        loads(data)

        return {
            "statusCode": 200,
            "body": data,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }

    except s3.exceptions.NoSuchKey:
        return {
            "statusCode": 404,
            "body": dumps({
                "error": "Calendar data not found",
                "message": f"No data available for {year}/{month:02d}"
            }),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }

    except s3.exceptions.NoSuchBucket:
        return {
            "statusCode": 500,
            "body": dumps({"error": "Configuration error: S3 bucket not found"}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }

    except JSONDecodeError as e:
        return {
            "statusCode": 500,
            "body": dumps({"error": "Data format error"}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": dumps({"error": "Internal server error"}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }

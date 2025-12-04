import boto3
import json
import os
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize S3 client
S3_BUCKET = os.environ.get("S3_BUCKET")
s3 = boto3.client("s3")


def lambda_handler(event, context):
    """
    AWS Lambda handler for API Gateway endpoint: /calendar/{year}/{month}
    Retrieves filtered companies data from S3 bucket for the specified year and month.
    """
    logger.info(f"Event: {json.dumps(event)}")

    # Extract path parameters
    path_params = event.get("pathParameters", {})
    year = path_params.get("year")
    month = path_params.get("month")

    # Validate required parameters
    if not year or not month:
        logger.error("Missing required path parameters: year or month")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing year or month parameters"}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }

    # Validate year and month are numeric
    try:
        year_int = int(year)
        month_int = int(month)

        # Validate month range
        if month_int < 1 or month_int > 12:
            raise ValueError("Month must be between 1 and 12")

    except ValueError as e:
        logger.error(f"Invalid year or month format: {e}")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": f"Invalid year or month format: {str(e)}"}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }

    # Build S3 key
    key = f"{year_int}/{month_int:02d}/filtered_companies.json"
    logger.info(f"Attempting to read from S3: bucket={S3_BUCKET}, key={key}")

    try:
        # Retrieve object from S3
        response = s3.get_object(Bucket=S3_BUCKET, Key=key)
        data = response["Body"].read().decode("utf-8")

        # Validate it's valid JSON
        json.loads(data)  # This will raise an exception if invalid JSON

        logger.info(f"Successfully retrieved data from S3: {key}")
        return {
            "statusCode": 200,
            "body": data,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }

    except s3.exceptions.NoSuchKey:
        logger.error(f"File not found in S3: {key}")
        return {
            "statusCode": 404,
            "body": json.dumps({
                "error": "Calendar data not found",
                "message": f"No data available for {year}/{month:02d}"
            }),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }

    except s3.exceptions.NoSuchBucket:
        logger.error(f"S3 bucket not found: {S3_BUCKET}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Configuration error: S3 bucket not found"}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in S3 file: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Data format error"}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }

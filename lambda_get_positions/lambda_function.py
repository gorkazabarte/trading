import json
import os
from typing import Dict, Any

import boto3
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')

S3_BUCKET = os.environ.get('S3_BUCKET', 'dev-trading-data-storage')


def build_s3_key(year: str, month: str, day: str) -> str:
    return f"{year}/{month}/{day}/positions.json"


def create_error_response(status_code: int, message: str) -> Dict[str, Any]:
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({'error': message})
    }


def create_success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(data)
    }


def extract_date_from_body(event: Dict[str, Any]) -> tuple:
    try:
        body = json.loads(event.get('body', '{}'))
        year = body.get('year')
        month = body.get('month')
        day = body.get('day')

        if not all([year, month, day]):
            return None, None, None

        return str(year), str(month), str(day)
    except json.JSONDecodeError:
        return None, None, None


def fetch_positions_from_s3(s3_key: str) -> Dict[str, Any]:
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        content = response['Body'].read().decode('utf-8')
        return json.loads(content)
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            raise FileNotFoundError(f"No positions file found for the specified date")
        raise Exception(f"S3 error: {str(e)}")


def format_positions_response(positions: Dict[str, Any], year: str, month: str, day: str) -> Dict[str, Any]:
    return {
        'date': f"{year}-{month.zfill(2)}-{day.zfill(2)}",
        'count': len(positions),
        'positions': positions
    }


def lambda_handler(event, context):
    year, month, day = extract_date_from_body(event)

    if not all([year, month, day]):
        return create_error_response(400, 'Missing required fields: year, month, day')

    s3_key = build_s3_key(year, month, day)

    try:
        positions = fetch_positions_from_s3(s3_key)
        response_data = format_positions_response(positions, year, month, day)
        return create_success_response(response_data)
    except FileNotFoundError as e:
        return create_error_response(404, str(e))
    except Exception as e:
        return create_error_response(500, f"Internal server error: {str(e)}")


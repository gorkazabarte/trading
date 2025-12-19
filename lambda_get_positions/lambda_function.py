import json
import os
from typing import Dict, Any

import boto3
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')

S3_BUCKET = os.environ.get('S3_BUCKET', 'dev-trading-data-storage')
S3_KEY = 'open_positions.json'


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


def fetch_positions_from_s3() -> Dict[str, Any]:
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=S3_KEY)
        content = response['Body'].read().decode('utf-8')
        return json.loads(content)
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            raise FileNotFoundError("No positions file found")
        raise Exception(f"S3 error: {str(e)}")


def format_positions_response(positions: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'count': len(positions),
        'positions': positions
    }


def lambda_handler(event, context):
    try:
        positions = fetch_positions_from_s3()
        response_data = format_positions_response(positions)
        return create_success_response(response_data)
    except FileNotFoundError as e:
        return create_error_response(404, str(e))
    except Exception as e:
        return create_error_response(500, f"Internal server error: {str(e)}")



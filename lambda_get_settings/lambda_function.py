import json
import os
from boto3 import client

s3_client = client('s3')

S3_BUCKET = os.environ.get('S3_BUCKET', 'dev-trading-data-storage')
S3_KEY = 'settings.json'


def create_response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'GET,OPTIONS'
        },
        'body': json.dumps(body)
    }


def get_settings_from_s3():
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=S3_KEY)
        settings_content = response['Body'].read().decode('utf-8')
        settings = json.loads(settings_content)
        return settings
    except s3_client.exceptions.NoSuchKey:
        return None
    except Exception as e:
        raise e


def lambda_handler(event, context):
    try:
        if event.get('httpMethod') == 'OPTIONS':
            return create_response(200, {})

        settings = get_settings_from_s3()

        if settings is None:
            return create_response(404, {
                'error': 'Settings file not found',
                'message': f's3://{S3_BUCKET}/{S3_KEY} does not exist'
            })

        return create_response(200, settings)

    except Exception as e:
        return create_response(500, {
            'error': 'Internal server error',
            'message': str(e)
        })


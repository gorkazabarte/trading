import json
import boto3
from botocore.exceptions import ClientError


def create_response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(body)
    }


def get_bucket_name():
    import os
    bucket = os.environ.get('S3_BUCKET')
    if not bucket:
        raise ValueError('S3_BUCKET environment variable not set')
    return bucket


def get_status_from_s3(s3_client, bucket):
    try:
        response = s3_client.get_object(Bucket=bucket, Key='status.json')
        status_data = json.loads(response['Body'].read().decode('utf-8'))
        return status_data
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            return None
        raise


def lambda_handler(event, context):
    try:
        bucket = get_bucket_name()
        s3_client = boto3.client('s3')

        status_data = get_status_from_s3(s3_client, bucket)

        if status_data is None:
            return create_response(404, {
                'error': 'Status file not found. Application may not be running.'
            })

        return create_response(200, status_data)

    except ValueError as e:
        return create_response(500, {'error': str(e)})
    except Exception as e:
        return create_response(500, {'error': f'Failed to retrieve status: {str(e)}'})

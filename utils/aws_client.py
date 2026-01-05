"""
AWS S3 client management and operations.
"""
from typing import Dict
from boto3 import client
from os import environ


def get_aws_credentials() -> Dict[str, str]:
    return {
        'access_key': environ.get('AWS_ACCESS_KEY_ID'),
        'secret_key': environ.get('AWS_SECRET_ACCESS_KEY'),
        'region': environ.get('AWS_DEFAULT_REGION', 'us-west-2')
    }


def validate_aws_credentials(credentials: Dict) -> bool:
    return credentials['access_key'] is not None and credentials['secret_key'] is not None


def create_s3_client():
    credentials = get_aws_credentials()

    if not validate_aws_credentials(credentials):
        raise ValueError("AWS credentials not found in environment variables")

    return client(
        's3',
        aws_access_key_id=credentials['access_key'],
        aws_secret_access_key=credentials['secret_key'],
        region_name=credentials['region']
    )


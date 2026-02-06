"""
AWS S3 client management and operations.
"""
from datetime import datetime, timezone
from json import dumps
from os import environ
from typing import Dict

from boto3 import client
from pytz import timezone as pytz_timezone


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


def get_spanish_time_formatted() -> str:
    spanish_tz = pytz_timezone('Europe/Madrid')
    spanish_time = datetime.now(timezone.utc).astimezone(spanish_tz)
    return spanish_time.strftime('%-m/%-d/%Y, %-I:%M:%S %p')


def upload_status_to_s3(s3_client, bucket: str, mode: str):
    status_data = {
        "time": get_spanish_time_formatted(),
        "mode": mode
    }

    s3_client.put_object(
        Bucket=bucket,
        Key='status.json',
        Body=dumps(status_data, indent=2),
        ContentType='application/json'
    )



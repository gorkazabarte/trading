from json import dumps, loads
from os import environ
from datetime import datetime, timedelta

from boto3 import client


s3_client = client('s3')
S3_BUCKET = environ.get('S3_BUCKET', 'dev-trading-data-storage')


def calculate_statistics(positions):
    if not positions:
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_profit': 0.0,
            'avg_profit_per_trade': 0.0,
            'win_rate': 0.0
        }

    total_trades = len(positions)
    winning_trades = sum(1 for p in positions if p.get('profit', 0) > 0)
    losing_trades = sum(1 for p in positions if p.get('profit', 0) < 0)
    total_profit = sum(p.get('profit', 0) for p in positions)
    avg_profit = total_profit / total_trades if total_trades > 0 else 0
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

    return {
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'total_profit': round(total_profit, 2),
        'avg_profit_per_trade': round(avg_profit, 2),
        'win_rate': round(win_rate, 2)
    }


def get_date_range(days_back):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    date_list = []
    current_date = start_date

    while current_date <= end_date:
        year = current_date.year
        month = current_date.month
        day = current_date.day
        date_list.append((year, month, day))
        current_date += timedelta(days=1)

    return date_list


def load_closed_positions_for_date(year, month, day):
    s3_key = f"{year}/{month:02d}/{day:02d}/closed_positions.json"

    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        data = loads(response['Body'].read().decode('utf-8'))
        return data if isinstance(data, list) else []
    except s3_client.exceptions.NoSuchKey:
        return []
    except Exception:
        return []


def lambda_handler(event, context):
    try:
        body = loads(event.get('body', '{}')) if isinstance(event.get('body'), str) else event.get('body', {})
        days_back = body.get('days', 5)

        if not isinstance(days_back, int) or days_back < 1 or days_back > 365:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': dumps({'error': 'days must be an integer between 1 and 365'})
            }

        date_range = get_date_range(days_back)
        all_positions = []

        for year, month, day in date_range:
            positions = load_closed_positions_for_date(year, month, day)
            all_positions.extend(positions)

        stats = calculate_statistics(all_positions)

        response_data = {
            'period': f'Last {days_back} days',
            'statistics': stats,
            'positions': all_positions
        }

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': dumps(response_data)
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': dumps({'error': f'Failed to retrieve closed positions: {str(e)}'})
        }

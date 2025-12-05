from boto3 import resource
from json import JSONDecodeError, JSONEncoder, loads, dumps
from os import environ
from decimal import Decimal

dynamodb = resource('dynamodb')
DYNAMODB_TABLE = environ.get('DYNAMODB_TABLE')
table = dynamodb.Table(DYNAMODB_TABLE)


class DecimalEncoder(JSONEncoder):
    """Helper class to convert Decimal to float for JSON serialization"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


def lambda_handler(event, context):
    """
    AWS Lambda handler for updating DynamoDB table.
    Expects a JSON body with stopLoss, takeProfit, nextInvestment, and opsPerDay values.
    Each setting is stored as a separate item in DynamoDB with 'Setting' as partition key.
    """

    print(f"Received event: {event}")

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
                    "Access-Control-Allow-Origin": "*"
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
                    "Access-Control-Allow-Origin": "*"
                }
            }

        updated_items = {}

        for setting_name in required_settings:
            setting_value = body[setting_name]

            if isinstance(setting_value, float):
                setting_value = Decimal(str(setting_value))

            table.put_item(
                Item={
                    'Setting': setting_name,
                    'Value': setting_value
                }
            )

            updated_items[setting_name] = setting_value
            print(f"Updated setting: {setting_name} = {setting_value}")

        return {
            "statusCode": 200,
            "body": dumps({
                "message": "Settings updated successfully",
                "updatedSettings": updated_items
            }, cls=DecimalEncoder),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }

    except JSONDecodeError as e:
        return {
            "statusCode": 400,
            "body": dumps({"error": "Invalid JSON format"}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }

    except dynamodb.meta.client.exceptions.ResourceNotFoundException:
        return {
            "statusCode": 500,
            "body": dumps({"error": "Configuration error: DynamoDB table not found"}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }

    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        return {
            "statusCode": 409,
            "body": dumps({"error": "Item could not be updated due to conditional check failure"}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": dumps({"error": f"Internal server error {e}"}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }


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
    Expects a JSON body with the item data to update.
    """

    print(f"Received event: {event}")

    try:
        if 'body' in event:
            if isinstance(event['body'], str):
                body = loads(event['body'])
            else:
                body = event['body']
                print(f"Body: {body}")
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

        if 'stopLoss' not in body or 'takeProfit' not in body or 'nextInvestment' not in body or 'opsPerDay' not in body:
            print(f"Body missing required fields: {body}")
            return {
                "statusCode": 400,
                "body": dumps({"error": "Missing required field in the body"}),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                }
            }

        item_id = body.pop('id')

        update_expression = "SET "
        expression_attribute_names = {}
        expression_attribute_values = {}

        for idx, (key, value) in enumerate(body.items()):
            attr_name = f"#attr{idx}"
            attr_value = f":val{idx}"

            if idx > 0:
                update_expression += ", "

            update_expression += f"{attr_name} = {attr_value}"
            expression_attribute_names[attr_name] = key

            if isinstance(value, float):
                expression_attribute_values[attr_value] = Decimal(str(value))
            else:
                expression_attribute_values[attr_value] = value

        # Update the item in DynamoDB
        response = table.update_item(
            Key={'id': item_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues="ALL_NEW"
        )

        return {
            "statusCode": 200,
            "body": dumps({
                "message": "Item updated successfully",
                "updatedItem": response.get('Attributes', {})
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
            "body": dumps({"error": "Internal server error"}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }


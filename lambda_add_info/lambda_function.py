def lambda_handler(event, context):

    try:

        companies: list = event.get("companies", [])


        return {
            'statusCode': 200,
            'body': 'Earnings data for today uploaded to S3.'
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': f'Error: {str(e)}'
        }

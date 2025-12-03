def lambda_handler(event, context):

    print(f'[INFO] Event {event}')
    print(f'[INFO] Context {context}')

    return {
        "Body": event
    }

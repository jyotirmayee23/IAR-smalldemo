import os
import json
from aws_lambda_powertools import Logger
import boto3

MEMORY_TABLE = os.environ["MEMORY_TABLE"]

ddb = boto3.resource("dynamodb")
memory_table = ddb.Table(MEMORY_TABLE)
logger = Logger()

def clear_history(conversation_id):
    try:
        memory_table.update_item(
            Key={"SessionId": conversation_id},
            UpdateExpression="SET History = :empty",
            ExpressionAttributeValues={":empty": []}
        )
        return True
    except Exception as e:
        logger.error(f"Failed to clear history in conversation {conversation_id}: {str(e)}")
        return False

@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, context):
    # Parse the body of the event as JSON
    body = json.loads(event['body'])
    print("conversations body " , body)

    # Extract conversation_ids from the parsed body
    conversation_ids = body.get('conversation_ids')
    print("conversation ids " , conversation_ids)

    if not conversation_ids or not isinstance(conversation_ids, list):
        return {
            "statusCode": 400,
            "body": json.dumps({"message": "Bad Request. Conversation IDs must be provided in an array."})
        }

    success = True
    for conversation_id in conversation_ids:
        # Clear the "History" field within each conversation identified by conversation_id
        success &= clear_history(conversation_id)

    if success:
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "*",
            },
            "body": json.dumps({"message": "History cleared from conversations successfully!"})
        }
    else:
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Failed to clear history from one or more conversations."})
        }

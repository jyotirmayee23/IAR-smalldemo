import os
import json
from aws_lambda_powertools import Logger
import boto3

MEMORY_TABLE = os.environ["MEMORY_TABLE"]
DOCUMENT_TABLE = os.environ["DOCUMENT_TABLE"]
BUCKET = os.environ["BUCKET"]  # Add the environment variable for the S3 bucket
ddb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
memory_table = ddb.Table(MEMORY_TABLE)
document_table = ddb.Table(DOCUMENT_TABLE)
logger = Logger()

def clear_session(conversation_id):
    try:
        memory_table.delete_item(
            Key={"SessionId": conversation_id}
        )
        return True
    except Exception as e:
        logger.error(f"Failed to clear session in conversation {conversation_id}: {str(e)}")
        return False

def delete_objects_in_folder(bucket, path):
    try:
        # List all objects in the specified path (prefix)
        response = s3.list_objects(Bucket=bucket, Prefix=path)

        # Check if there are any objects to delete
        if 'Contents' in response:
            objects_to_delete = [{'Key': obj['Key']} for obj in response['Contents']]

            # Delete all objects in the specified path
            s3.delete_objects(Bucket=bucket, Delete={'Objects': objects_to_delete})

            logger.info(f"All objects in path {path} deleted successfully")
            return True
        else:
            logger.info(f"No objects found in path {path}")
            return False
    except Exception as e:
        logger.error(f"Failed to delete objects in path {path}: {str(e)}")
        return False

def delete_document(user_id, document_id):
    try:
        response = document_table.get_item(
            Key={"userid": user_id, "documentid": document_id}
        )

        if 'Item' in response:
            document_item = response['Item']
            filename = document_item.get('filename', None)

            if filename:
                # Delete the document item from the table
                document_table.delete_item(
                    Key={"userid": user_id, "documentid": document_id}
                )

                # Delete all objects inside the specified path in S3
                path_in_s3 = f"{user_id}/{filename}"
                success_delete_objects = delete_objects_in_folder(BUCKET, path_in_s3)

                return success_delete_objects
            else:
                logger.info(f"No filename found for document {document_id}")
                return False
        else:
            logger.info(f"No document found for user {user_id}")
            return False
    except Exception as e:
        logger.error(f"Failed to delete document for user {user_id}: {str(e)}")
        return False

@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, context):
    claims = event['requestContext']['authorizer']['claims']
    user_id = claims['cognito:username']
    
    body = json.loads(event['body'])
    document_id = body.get('document_id')
    conversation_ids = body.get('conversation_ids', [])

    print("conversation_ids" , conversation_ids)
    print("document_id" , document_id)

    if not user_id or not document_id or not conversation_ids:
        return {
            "statusCode": 400,
            "body": json.dumps({"message": "Bad Request. User ID, Document ID, and Conversation IDs are required."})
        }

    success_clear_session = True

    for conversation_id in conversation_ids:
        success_clear_session = success_clear_session and clear_session(conversation_id)

    success_delete_document = delete_document(user_id, document_id)

    if success_clear_session and success_delete_document:
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "*",
            },
            "body": json.dumps({"message": "Sessions cleared, document deleted, and S3 objects removed successfully!"})
        }
    else:
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Sessions cleared, document deleted, and  S3 objects removed successfully!"})
        }

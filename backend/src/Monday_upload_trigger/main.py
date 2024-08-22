import os, json
from datetime import datetime
import boto3
import PyPDF2
# import shortuuid
import urllib
# import shutil
import uuid
import requests
from aws_lambda_powertools import Logger
from decimal import Decimal


DOCUMENT_TABLE = os.environ["DOCUMENT_TABLE"]
MEMORY_TABLE = os.environ["MEMORY_TABLE"]

queue_name = os.environ.get("QUEUE", "")

if "2Queue" in queue_name:
    # Set the value of the QUEUE variable to the queue name
    os.environ["QUEUE"] = queue_name
    print(f"Set QUEUE variable to: {queue_name}")
else:
    print("The environment variable QUEUE does not contain '2Queue'")

QUEUE = queue_name
print(QUEUE)

ddb = boto3.resource("dynamodb")
document_table = ddb.Table(DOCUMENT_TABLE)
memory_table = ddb.Table(MEMORY_TABLE)
sqs = boto3.client("sqs")
s3 = boto3.client("s3")
logger = Logger()

@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, context):
    claims = event['requestContext']['authorizer']['claims']
    user_id = claims['cognito:username']
    # Parse the body of the event as JSON
    body = json.loads(event['body'])

    # Extract public_url, name, and userid from the parsed body
    public_url = body['public_url']
    name = body['name']
    print(user_id)

    document_id = str(uuid.uuid4())

    # Download the file from the public_url
    response = requests.get(public_url, stream=True)
    file_name = name
    with open(f"/tmp/{file_name}", 'wb') as out_file:
        out_file.write(response.content)
        
    file_extension = os.path.splitext(file_name)[1].lower()
    file_size = os.path.getsize(f"/tmp/{file_name}")

    conversation_id = str(uuid.uuid4())

    timestamp = datetime.utcnow()
    timestamp_str = timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    document = {
        "userid": user_id,
        "documentid": document_id,
        "filename": file_name,
        "created": timestamp_str,
        # "pages": pages,
        "filesize": file_size,
        "docstatus": "UPLOADED",
        "conversations": [],
    }

    conversation = {"conversationid": conversation_id, "created": timestamp_str}
    document["conversations"].append(conversation)

    document_table.put_item(Item=document)

    conversation = {"SessionId": conversation_id, "History": []}
    memory_table.put_item(Item=conversation)

    message = {
        "documentid": document_id,
        "user": user_id,
        "public_url": public_url,
        "file_name": file_name # Add public_url to the message
    }
    sqs.send_message(QueueUrl=QUEUE, MessageBody=json.dumps(message))

    return {
    "statusCode": 200,
    "headers": {
        "Content-Type": "application/json",
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "*",
    },
    "body": json.dumps({"message": "File uploaded successfully!"})  # Add any additional response data as needed
}

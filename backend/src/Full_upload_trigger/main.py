import os
import json
from datetime import datetime
import boto3
import PyPDF2
import shortuuid
import urllib
from aws_lambda_powertools import Logger

DOCUMENT_TABLE = os.environ["DOCUMENT_TABLE"]
MEMORY_TABLE = os.environ["MEMORY_TABLE"]
QUEUE = os.environ["QUEUE"]
BUCKET = os.environ["BUCKET"]

ddb = boto3.resource("dynamodb")
document_table = ddb.Table(DOCUMENT_TABLE)
memory_table = ddb.Table(MEMORY_TABLE)
sqs = boto3.client("sqs")
s3 = boto3.client("s3")
logger = Logger()

def fetch_filenames_from_folder(bucket, folder):
    response = s3.list_objects_v2(Bucket=bucket, Prefix=folder)
    filenames = []
    if "Contents" in response:
        for obj in response["Contents"]:
            filename = obj["Key"].split("/")[-1]
            filenames.append(filename)
    return filenames

@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, context):
    print("event", event)
    print("Fetching filenames from S3 folders...")
    all_filenames = []
    for folder in ["pdf", "csv", "txt", "docx"]:
        all_filenames.extend(fetch_filenames_from_folder(BUCKET, folder))
    print("All Filenames fetched:", all_filenames)
    
    user_id = event["requestContext"]["authorizer"]["claims"]["sub"]
    # Join all filenames with commas
    all_filenames_str = ",".join(all_filenames)


    # Example: create/update DynamoDB record
    document_id = shortuuid.uuid()
    timestamp_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
    document = {
        "userid": user_id,
        "documentid": document_id,
        "filename": all_filenames_str,
        "created": timestamp_str,
        "docstatus": "UPLOADED",
        "conversations": []
    }
    document_table.put_item(Item=document)

    # Example: send message to SQS
    message = {
        "documentid": document_id,
        "user": user_id,
    }
    sqs.send_message(QueueUrl=QUEUE, MessageBody=json.dumps(message))

    print("All Filenames stored and processed.")

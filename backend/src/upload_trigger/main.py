import os, json
from datetime import datetime
import boto3
import PyPDF2
import shortuuid
import urllib
from aws_lambda_powertools import Logger
 
DOCUMENT_TABLE = os.environ["DOCUMENT_TABLE"]
MEMORY_TABLE = os.environ["MEMORY_TABLE"]
QUEUE1 = os.environ["QUEUE1"]
QUEUE2 = os.environ["QUEUE2"]
BUCKET = os.environ["BUCKET"]
 
 
ddb = boto3.resource("dynamodb")
document_table = ddb.Table(DOCUMENT_TABLE)
memory_table = ddb.Table(MEMORY_TABLE)
sqs = boto3.client("sqs")
s3 = boto3.client("s3")
logger = Logger()
 
 
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, context):
    print("events",event)
 
    key = urllib.parse.unquote_plus(event["Records"][0]["s3"]["object"]["key"])
    split = key.split("/")
    user_id = split[1]
    file_name1=split[2]
    file_name = key.split("/")[-1]
    print(user_id)
    ext=os.path.splitext(file_name)[1].lower()
    list=['.mp4','.mov','.m4v']
   
    file_name_encoded = file_name1.replace(" ", "+")
 
    print("file name " , file_name)
    print("key " , key)  
 
   
    if ext in list:
        print("video uploaded triggered")
        message1 = {
            "key": key,
            "user": user_id,
        }
        sqs.send_message(QueueUrl=QUEUE2, MessageBody=json.dumps(message1))
    else:
       
        document_id = shortuuid.uuid()
 
        # s3.download_file(BUCKET, key, f"/tmp/{file_name}")
 
        s3_object_url = f"uploads/{user_id}/{file_name_encoded}/{file_name_encoded}"
 
        # with open(f"/tmp/{file_name}", "rb") as f:
        #     reader = PyPDF2.PdfReader(f)
        #     pages = str(len(reader.pages))
        response = s3.head_object(Bucket=BUCKET, Key=s3_object_url)
 
# Extract the file size in bytes
        conversation_id = shortuuid.uuid()
 
        timestamp = datetime.utcnow()
        timestamp_str = timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
 
        document = {
            "userid": user_id,
            "documentid": document_id,
            "filename": file_name1,
            "created": timestamp_str,
            # "pages": pages,
            "filesize": response['ContentLength'],
            "docstatus": "UPLOADED",
            "conversations": [],
            "s3_object_url": s3_object_url
        }
 
        conversation = {"conversationid": conversation_id, "created": timestamp_str}
        document["conversations"].append(conversation)
 
        document_table.put_item(Item=document)
 
        conversation = {"SessionId": conversation_id, "History": []}
        memory_table.put_item(Item=conversation)
        message = {
            "documentid": document_id,
            "key": key,
            "user": user_id,
        }
        sqs.send_message(QueueUrl=QUEUE1, MessageBody=json.dumps(message))
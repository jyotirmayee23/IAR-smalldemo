import os
import json
import boto3
from botocore.config import Config
import shortuuid
from aws_lambda_powertools import Logger

BUCKET = os.environ["BUCKET"]
REGION = os.environ["REGION"]

s3 = boto3.client(
    "s3",
    endpoint_url=f"https://s3.{REGION}.amazonaws.com",
    config=Config(
        s3={"addressing_style": "virtual"}, region_name=REGION, signature_version="s3v4"
    ),
)
logger = Logger()


def s3_key_exists(bucket, key):
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except Exception as e:
        return False


@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, context):
    # Split the 'files' parameter into a list of file names
    files_param = event["queryStringParameters"]["files"]
    files = files_param.split(',')
    
    response_data = []

    for file_name_full in files:
        file_name, extension = os.path.splitext(file_name_full)
        
        # Define the folder based on the file extension
        folder = get_folder(extension)
        
        # Check if the file exists in the specific folder
        exists = s3_key_exists(BUCKET, f"{folder}/{file_name_full}")
        
        logger.info(
            {
                "file_name_full": file_name_full,
                "file_name": file_name,
                "exists": exists,
            }
        )

        if exists:
            suffix = shortuuid.ShortUUID().random(length=4)
            key = f"allinone/{folder}/{file_name}-{suffix}{extension}"
        else:
            key = f"allinone/{folder}/{file_name}{extension}"

        content_type = get_content_type(extension)
        
        presigned_url = s3.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": BUCKET,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=300,
            HttpMethod="PUT",
        )

        response_data.append({"file_name": file_name_full, "presignedurl": presigned_url})

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
        },
        "body": json.dumps(response_data),
    }

def get_folder(extension):
    if extension.lower() == ".pdf":
        return "pdf"
    elif extension.lower() == ".csv":
        return "csv"
    elif extension.lower() == ".txt":
        return "txt"
    elif extension.lower() == ".docx":
        return "docx"
    else:
        return "other"

def get_content_type(extension):
    if extension.lower() == ".pdf":
        return "application/pdf"
    elif extension.lower() == ".csv":
        return "text/csv"
    elif extension.lower() == ".txt":
        return "text/plain"
    elif extension.lower() == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        return "application/octet-stream"

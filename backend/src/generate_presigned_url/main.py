import os, json
import boto3
from botocore.config import Config
import shortuuid
import re
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
 
def check_filename(filename):
    """
    Sanitize the filename to be S3-compatible by:
    - Replacing spaces with underscores
    - Removing special characters except for hyphens, underscores, and periods
    """
    # Replace spaces with underscores
    sanitized = filename.replace(" ", "_")
   
    # Remove special characters except hyphens, underscores, and periods
    sanitized = re.sub(r'[^a-zA-Z0-9._-]', '', sanitized)
   
    # Ensure the filename does not start with a hyphen or underscore
    sanitized = re.sub(r'^[-_]+', '', sanitized)
   
    return sanitized
 
def s3_key_exists(bucket, key):
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except:
        return False
 
 
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, context):
    user_id = event["requestContext"]["authorizer"]["claims"]["sub"]
    file_name_full = event["queryStringParameters"]["file_name"]
    file_name, extension = os.path.splitext(file_name_full)
 
    exists = s3_key_exists(BUCKET, f"uploads/{user_id}/{file_name_full}/{file_name_full}")
 
    logger.info(
        {
            "user_id": user_id,
            "file_name_full": file_name_full,
            "file_name": file_name,
            "exists": exists,
        }
    )
 
    if exists:
        suffix = shortuuid.ShortUUID().random(length=4)
        # Separate the filename and extension for CSV file
        base_name, extension = os.path.splitext(file_name_full)
        key = f"uploads/{user_id}/{base_name}-{suffix}{extension}/{base_name}-{suffix}{extension}"
    else:
        file_name1=check_filename(file_name)
        key = f"uploads/{user_id}/{file_name1}{extension}/{file_name1}{extension}"
 
    print("key after condition" , key)
 
 
    if extension.lower() == ".pdf":
        content_type = "application/pdf"
    elif extension.lower() == ".csv":
        content_type = "text/csv"
    elif extension.lower() == ".txt":
        content_type = "text/plain"
    elif extension.lower() == ".docx":
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif extension.lower() == ".mp4":
        content_type = "video/mp4"
    elif extension.lower() == ".m4v":
        content_type = "video/x-m4v"
    elif extension.lower() == ".mov":
        content_type = "video/quicktime"
    else:
        content_type = "application/octet-stream"
 
    print("content type" , content_type)
   
    presigned_url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": BUCKET,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=500,
        HttpMethod="PUT",
    )
    print(presigned_url)
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
        },
        "body": json.dumps({"presignedurl": presigned_url}),
    }
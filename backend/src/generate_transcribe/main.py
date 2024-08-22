import os, json
import boto3
import time
import random
from aws_lambda_powertools import Logger
 
 
DOCUMENT_TABLE = os.environ["DOCUMENT_TABLE"]
BUCKET = os.environ["BUCKET"]
 
transcribe = boto3.client('transcribe')
s3 = boto3.client("s3")
ddb = boto3.resource("dynamodb")
document_table = ddb.Table(DOCUMENT_TABLE)
logger = Logger()
 
 
 
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, context):
    event_body = json.loads(event["Records"][0]["body"])
    key = event_body["key"]
    user_id = key.split("/")[1]
    file_name_full = key.split("/")[-1]
    folder_path = '/'.join(key.split('/')[:-1])
 
    print("event_body" , event_body)
    print("context" , context)
    print("user_id" , user_id)
    print("key" , key)
    print("file_name_full" , file_name_full)
    print("folder_path" , folder_path)
 
 
    #s3.download_file(BUCKET, key, f"/tmp/{file_name_full}")
    file_extension = os.path.splitext(file_name_full)[1].lower()
    list=['.mp4','.mov','.m4v']
    if file_extension in list:
        job_id = 'Job_' + str(random.randint(0, 100))
        response = transcribe.start_transcription_job(
            TranscriptionJobName=job_id,
            IdentifyLanguage=True,
            Media={
                'MediaFileUri': f's3://{BUCKET}/{key}'
            },
            OutputBucketName=BUCKET,
            OutputKey=f'{folder_path}/{job_id}.json'
        )
        print(job_id)      
    else:
        raise ValueError(f"Unsupported file type: {file_extension}")
 
    # loader = PyPDFLoader(f"/tmp/{file_name_full}")
    while True:
            job_status = transcribe.get_transcription_job(TranscriptionJobName=job_id)['TranscriptionJob']['TranscriptionJobStatus']
            if job_status == 'COMPLETED':
                break
            elif job_status == 'FAILED':
                print(f"Transcription job {job_id} failed. Exiting.")
                return
            time.sleep(5)  # Wait for 5 seconds before checking again
       
        # Delete the transcription job
    transcribe.delete_transcription_job(TranscriptionJobName=job_id)
    print(f"Transcription job {job_id} deleted.")
    response = s3.get_object(Bucket=BUCKET, Key=f'{folder_path}/{job_id}.json')
    json_data = response['Body'].read().decode('utf-8')
    data = json.loads(json_data)
    transcripts = data["results"]["transcripts"]
    content = " ".join(item["transcript"] for item in transcripts if "transcript" in item).strip()
 
    s3.put_object(Body=content, Bucket=BUCKET, Key=f"{folder_path}/job.txt")
    s3.delete_object(Bucket=BUCKET, Key=f'{folder_path}/{job_id}.json')
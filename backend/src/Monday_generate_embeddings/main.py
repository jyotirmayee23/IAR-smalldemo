import os
import json
import requests
import boto3
from aws_lambda_powertools import Logger
from langchain.embeddings import BedrockEmbeddings
from langchain.document_loaders import PyPDFLoader
from langchain.indexes import VectorstoreIndexCreator
from langchain.vectorstores import FAISS
from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain.document_loaders import Docx2txtLoader
from langchain.document_loaders import TextLoader
# from langchain_community.document_loaders import UnstructuredExcelLoader
# from langchain_community.document_loaders import UnstructuredPowerPointLoader
from langchain_community.document_loaders import UnstructuredFileLoader
# from langchain_community.document_loaders import Docx2txtLoader
# from langchain_community.document_loaders.excel import UnstructuredExcelLoader
# from langchain.document_loaders import UnstructuredWordDocumentLoader

DOCUMENT_TABLE = os.environ["DOCUMENT_TABLE"]
BUCKET = os.environ["BUCKET"]

s3 = boto3.client("s3")
ddb = boto3.resource("dynamodb")
document_table = ddb.Table(DOCUMENT_TABLE)
logger = Logger()

def set_doc_status(user_id, document_id, status):
    document_table.update_item(
        Key={"userid": user_id, "documentid": document_id},
        UpdateExpression="SET docstatus = :docstatus",
        ExpressionAttributeValues={":docstatus": status},
    )

@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, context):
    event_body = json.loads(event["Records"][0]["body"])
    document_id = event_body["documentid"]
    user_id = event_body["user"]
    public_url = event_body["public_url"]
    file_name = event_body["file_name"]

    set_doc_status(user_id, document_id, "PROCESSING")

    response = requests.get(public_url, stream=True)
    with open(f"/tmp/{file_name}", 'wb') as out_file:
        out_file.write(response.content)
    
    file_path = f"/tmp/{file_name}"
    file_extension = os.path.splitext(file_name)[1].lower()

    if file_extension == ".pdf":
        loader = PyPDFLoader(f"/tmp/{file_name}")
    elif file_extension == ".csv":
        loader = CSVLoader(file_path=f"/tmp/{file_name}")
    elif file_extension == ".doc" or file_extension == ".docx" :
        loader = Docx2txtLoader(file_path=f"/tmp/{file_name}")
    elif file_extension == ".txt":
        loader = TextLoader(file_path=f"/tmp/{file_name}")
    else:
        raise ValueError(f"Unsupported file type: {file_extension}")

    # loader = PyPDFLoader(f"/tmp/{file_name}")

    bedrock_runtime = boto3.client(
        service_name="bedrock-runtime",
        region_name="us-east-1",
    )

    embeddings = BedrockEmbeddings(
        model_id="amazon.titan-embed-text-v1",
        client=bedrock_runtime,
        region_name="us-east-1",
    )

    index_creator = VectorstoreIndexCreator(
        vectorstore_cls=FAISS,
        embedding=embeddings,
    ) 

    index_from_loader = index_creator.from_loaders([loader])

    index_from_loader.vectorstore.save_local("/tmp")

    s3.upload_file(
        "/tmp/index.faiss", BUCKET, f"{user_id}/{file_name}/index.faiss"
    )
    s3.upload_file("/tmp/index.pkl", BUCKET, f"{user_id}/{file_name}/index.pkl")

    set_doc_status(user_id, document_id, "READY")

import os
import boto3
from aws_lambda_powertools import Logger
from langchain.embeddings import BedrockEmbeddings
from langchain.document_loaders import PyPDFLoader, CSVLoader, TextLoader, DirectoryLoader
from langchain_community.document_loaders import Docx2txtLoader  # Import Docx2txtLoader
from langchain.indexes import VectorstoreIndexCreator
from langchain.vectorstores import FAISS

DOCUMENT_TABLE = os.environ["DOCUMENT_TABLE"]
BUCKET = os.environ["BUCKET"]

s3 = boto3.client("s3")
ddb = boto3.resource("dynamodb")
document_table = ddb.Table(DOCUMENT_TABLE)
logger = Logger()

@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, context):
    folders_to_download = ['pdf/', 'csv/', 'txt/', 'docx/']

    # Iterate over each folder
    for folder in folders_to_download:
        # List objects in the specified bucket and folder
        response = s3.list_objects_v2(Bucket=BUCKET, Prefix=folder)

        # Check if the 'Contents' key exists in the response
        if 'Contents' in response:
            # Iterate over each object in the response
            for obj in response['Contents']:
                # Extract the file key (object name)
                file_key = obj['Key']
                
                # Check if the file key represents a folder
                if file_key.endswith('/'):
                    # Skip if it's a folder
                    continue

                # Extract the filename from the object key
                file_name = os.path.basename(file_key)
                # Define the local file path for download
                local_file_path = f"/tmp/{file_name}"

                # Download the file from S3 to the local file path
                s3.download_file(BUCKET, file_key, local_file_path)

                # Print a message indicating the file has been downloaded
                print(f"Downloaded file '{file_name}' to '{local_file_path}'")

    # Define a function to create a DirectoryLoader for a specific file type
    def create_directory_loader(file_type, directory_path='/tmp'):
        return DirectoryLoader(
            path=directory_path,
            glob=f"**/*{file_type}",
            loader_cls=loaders[file_type],
        )

    # Define a dictionary to map file extensions to their respective loaders
    loaders = {
        '.pdf': PyPDFLoader,
        '.csv': CSVLoader,
        '.txt': TextLoader,
        '.docx': Docx2txtLoader,  # Use Docx2txtLoader for DOCX files
    }

    # Create DirectoryLoader instances for each file type
    pdf_loader = create_directory_loader('.pdf')
    csv_loader = create_directory_loader('.csv')
    txt_loader = create_directory_loader('.txt')
    docx_loader = create_directory_loader('.docx')

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

    # Assuming you want to create an index from all loaders
    index_from_loaders = index_creator.from_loaders([pdf_loader, csv_loader, txt_loader, docx_loader])

    index_from_loaders.vectorstore.save_local("/tmp")

    # Upload the index files to S3
    s3.upload_file(
        "/tmp/index.faiss", BUCKET, f"/index.faiss"
    )
    s3.upload_file("/tmp/index.pkl", BUCKET, f"/index.pkl")

    # Assuming set_doc_status is defined elsewhere in your code
    # set_doc_status(user_id, document_id, "READY")

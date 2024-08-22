import os
import json
import boto3
from aws_lambda_powertools import Logger
from langchain.llms.bedrock import Bedrock
from langchain.memory.chat_message_histories import DynamoDBChatMessageHistory
from langchain.memory import ConversationBufferMemory
from langchain.embeddings import BedrockEmbeddings
from langchain.vectorstores import FAISS
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import PromptTemplate
 
 
MEMORY_TABLE = os.environ["MEMORY_TABLE"]
BUCKET = os.environ["BUCKET"]
 
 
s3 = boto3.client("s3")
logger = Logger()
 
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, context):
    event_body = json.loads(event["body"])
    logger.info(f"Event Body: {event_body}")
    file_name = event_body["fileName"]
    human_input = event_body["prompt"]
    conversation_id = event["pathParameters"]["conversationid"]
    model_id = event_body.get("model_id")
    language=event_body.get("language")
    if not language:
        language="en"
    print(language)
    logger.info(f"Received model_id: {model_id}")
    if not model_id:
        model_id="anthropic.claude-v2:1"
    #print(model_id)
 
    user = event["requestContext"]["authorizer"]["claims"]["sub"]
 
    s3.download_file(BUCKET, f"uploads/{user}/{file_name}/index.faiss", "/tmp/index.faiss")
    s3.download_file(BUCKET, f"uploads/{user}/{file_name}/index.pkl", "/tmp/index.pkl")
 
    bedrock_runtime = boto3.client(
        service_name="bedrock-runtime",
        region_name="us-east-1",
    )
 
    embeddings = BedrockEmbeddings(
        model_id="amazon.titan-embed-text-v1",
        client=bedrock_runtime,
        region_name="us-east-1",
    )
 
    MODEL_TYPE = "CLAUDE"
    if MODEL_TYPE == "CLAUDE":
        llm = Bedrock(
            model_id="anthropic.claude-v2:1",
            model_kwargs={"temperature": 0.7, "max_tokens_to_sample": 1000}
        )
        condense_question_llm = Bedrock(
            model_id="anthropic.claude-instant-v1",
            model_kwargs={"temperature": 0.7, "max_tokens_to_sample": 500}
        )
    else:
        llm = Bedrock(
            model_id="ai21.j2-ultra-v1",
            model_kwargs={"temperature": 0.7, "maxTokens": 700, "numResults": 1}
        )
        condense_question_llm = Bedrock(
            model_id="ai21.j2-mid-v1",
            model_kwargs={"temperature": 0.7, "maxTokens": 500, "numResults": 1}
        )
 
 
    #llm = Bedrock(
        #model_id=model_id,  # Use the dynamic model ID here
        #client=bedrock_runtime,
        #region_name="us-east-1"
             
    #)
   
    faiss_index = FAISS.load_local("/tmp", embeddings)
 
    message_history = DynamoDBChatMessageHistory(
        table_name=MEMORY_TABLE, session_id=conversation_id
    )
 
    memory = ConversationBufferMemory(
        memory_key="chat_history",
        chat_memory=message_history,
        input_key="question",
        output_key="answer",
        return_messages=True,
    )
    ext=os.path.splitext(file_name)[1].lower()
    list=['.mp4','.mov','.m4v']
    if ext in list:
        print("video")
        template = """You are an AI assistant tasked with summarizing video transcripts and answering questions about them. Using the following transcript of a video, provide a detailed and relevant response to the human's input. Please respond directly to the user's input, using the information from the video transcript. Do not mention that you're summarizing a transcript or that you have limited context. Just provide the relevant information as if you're directly answering the user's question or request.
 
        following is the video transcript:
        {context}
 
        Human: {question}
 
        Assistant: """
        custom_prompt=PromptTemplate(template=template, input_variables=["context", "question"])
        chat_history=[]
        qa = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=faiss_index.as_retriever(search_kwargs={"k": 7}),
            return_source_documents=True,
            combine_docs_chain_kwargs={"prompt": custom_prompt}
        )
        res = qa({"question": human_input,"chat_history":chat_history})
        if language.lower() != 'en':
            print("translation")
            translate = boto3.client('translate')
            try:
                translation = translate.translate_text(
                    Text=res["answer"],
                    SourceLanguageCode='en',
                    TargetLanguageCode=language
                )
                translated_text = translation['TranslatedText']
                res["answer"] = translated_text
                print(res["answer"])
                memory.save_context({"question": human_input}, {"answer": translated_text})
            except Exception as e:
                logger.error(f"Translation error: {str(e)}")
    else:
        qa = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=faiss_index.as_retriever(),
            memory=memory,
            return_source_documents=True,
        )
        res = qa({"question": human_input})
   
    logger.info(res)
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
        },
 
        "body": json.dumps(res["answer"])
    }
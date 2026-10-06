import os

from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI

load_dotenv()


def create_llm():
    return AzureChatOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        azure_deployment=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
        temperature=0,
    )

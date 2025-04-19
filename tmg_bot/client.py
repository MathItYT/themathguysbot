import os
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from openai import AzureOpenAI

project_client = AIProjectClient.from_connection_string(
    conn_str=os.getenv("AZURE_CONN_STR"),
    credential=DefaultAzureCredential(),
)
client: AzureOpenAI = project_client.inference.get_azure_openai_client(
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
)

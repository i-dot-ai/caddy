import os

from langchain_aws import BedrockEmbeddings
from langchain_core.embeddings import FakeEmbeddings
from langchain_openai import AzureOpenAIEmbeddings

from api.config import EMBEDDING_DIMENSION


def load_embedding_model(model_identifier: str):
    if model_identifier == "cohere.embed-english-v3":
        return BedrockEmbeddings(
            model_id=model_identifier, region_name=os.environ["OPENSEARCH_AWS_REGION"]
        )
    if model_identifier == "fake":
        return FakeEmbeddings(size=EMBEDDING_DIMENSION)
    if model_identifier == "text-embedding-3-large":
        return AzureOpenAIEmbeddings(
            model=model_identifier, chunk_size=1000, dimensions=EMBEDDING_DIMENSION
        )
    msg = "model_name=%s not recognised"
    raise ValueError(msg, model_identifier)

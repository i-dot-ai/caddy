import asyncio
import glob
import json
import os
from typing import Any, Callable, List

import pandas as pd
from langchain.document_loaders import DataFrameLoader
from langchain.embeddings import BedrockEmbeddings
from langchain_community.embeddings import AzureOpenAIEmbeddings
from langchain_core.embeddings import Embeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from opensearchpy import OpenSearch, helpers


def get_embeddings(model_id: str) -> tuple[Embeddings, int]:
    if model_id == "cohere.embed-english-v3":
        return BedrockEmbeddings(model_id=model_id, region_name="eu-west-3"), 1024
    if model_id == "text-embedding-3-large":
        return AzureOpenAIEmbeddings(model=model_id, chunk_size=1000), 3072
    raise ValueError(f"model_id={model_id} not supported")


class OpenSearchDocumentManager:
    def __init__(
        self, client: OpenSearch, index_name: str = "caddy-hybrid-search-index"
    ):
        self.client = client
        self.index_name = index_name
        self.embedding_model, self.dimension = get_embeddings(
            os.getenv("EMBEDDING_MODEL")
        )

    def create_index(self):
        index_body = {
            "settings": {"index": {"knn": True}},
            "mappings": {
                "properties": {
                    "text": {"type": "text"},
                    "source": {"type": "keyword"},
                    "domain": {"type": "keyword"},
                    "text_vector": {
                        "type": "knn_vector",
                        "dimension": self.dimension,
                        "method": {
                            "engine": "faiss",
                            "space_type": "l2",
                            "name": "hnsw",
                            "parameters": {},
                        },
                    },
                }
            },
        }
        # Delete index if it exists
        if self.client.indices.exists(index=self.index_name):
            print(f"Deleting index {self.index_name}")
            self.client.indices.delete(index=self.index_name)
        # Create new index
        self.client.indices.create(index=self.index_name, body=index_body)

    async def async_bulk_upload(self, file_path: str, domain: str = "citizen-advice"):
        json_files = glob.glob(os.path.join(file_path, "*.json"))
        for file in json_files:
            with open(file) as f:
                df = pd.DataFrame(json.load(f))

            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=2048,
                chunk_overlap=100,
                length_function=len,
            )

            loader = DataFrameLoader(df, page_content_column="markdown")
            docs = loader.load()

            if (domain == "citizen-advice") & ("source" in docs[0].metadata):
                docs = [d for d in docs if d.metadata["markdown_length"] > 1000]
                docs = [d for d in docs if "cymraeg" not in d.metadata["source"]]
            # move gov.uk source to be in same place
            elif domain == "gov_uk":
                for doc in docs:
                    doc.metadata["source"] = doc.metadata["source_url"]

            docs = text_splitter.split_documents(docs)

            embeddings = await self._gather_with_concurrency(
                10,
                *[
                    self.embedding_model.aembed_documents(
                        [d.page_content for d in docs]
                    )
                ],
            )
            success, failed = helpers.bulk(
                self.client, self._generate_bulk_actions(docs, embeddings, domain)
            )
            print(f"File Uploaded: {success}, Failed: {failed}")

    async def _gather_with_concurrency(
        self, concurrency: int, *coroutines: List[Callable]
    ) -> List[Any]:
        """Run a number of async coroutines with a concurrency limit.

        Args:
            concurrency (int): max number of concurrent coroutine runs.
            coroutines (List[Callable]): list of coroutines to run asynchronously.

        Returns:
            List[Any]: list of coroutine results.
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def semaphore_coroutine(coroutines):
            async with semaphore:
                return await coroutines

        return await asyncio.gather(*(semaphore_coroutine(c) for c in coroutines))

    def _generate_bulk_actions(self, documents, embeddings, domain="citizen-advice"):
        for i, (doc, vector) in enumerate(zip(documents, embeddings[0])):
            source = {
                "text": doc.page_content,
                "text_vector": vector,
                "domain": domain,
                **doc.metadata,  # Include all metadata fields
            }
            action = {"_index": self.index_name, "_source": source}
            yield action

from functools import partial
from typing import Any
from uuid import UUID

from langchain_core.documents import Document
from qdrant_client import models
from sqlmodel import Session

from api.environment import config
from api.models import Resource


def build_document(document: Document, session):
    """Convert Qdrant search result to Document with metadata enrichment."""
    resource = session.get(Resource, document.metadata["resource_id"])

    if not resource:
        return document

    if resource.url:
        document.metadata["url"] = resource.url
    else:
        s3_client = config.s3_client

        s3_url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": config.data_s3_bucket,
                "Key": f"{config.s3_prefix}/{resource.collection_id}/{resource.id}/{resource.filename}",
            },
            ExpiresIn=3600,
        )
        document.metadata["url"] = s3_url
        document.metadata["created_at"] = resource.created_at.strftime("%H:%M %d-%m-%Y")

    return document


def _qdrant_result_to_document(result_dict: dict[str, Any]) -> Document:
    """Convert Qdrant search result to LangChain Document."""
    payload = result_dict["payload"]

    page_content = payload.get("text", "")

    metadata = {
        "resource_id": payload.get("resource_id"),
        "collection_id": payload.get("collection_id"),
        "filename": payload.get("filename"),
        "content_type": payload.get("content_type"),
        "created_at": payload.get("created_at"),
        "order": payload.get("order"),
        "score": result_dict.get("score"),
    }

    metadata = {k: v for k, v in metadata.items() if v is not None}

    return Document(page_content=page_content, metadata=metadata)


async def search_collection(
    collection_id: UUID,
    query: str,
    session: Session,
    keywords: list[str] | None = None,
) -> list[Document]:
    """Query Qdrant vector store.

    Args:
        - collection_id (UUID): The collection to search in
        - query (str): The query text
        - session (Session): Database session
        - keywords: list(str):
            - Extract 3-5 specific terms that capture key issues or needs
            - Include amounts, dates, or specific services mentioned
            - Focus on actionable terms that could help find relevant documents
            - Avoid generic words or category names

    Returns:
        Documents: relevant documents
    """
    query_vector = config.embedding_model.embed_documents([query])[0]

    must_conditions = [
        models.FieldCondition(
            key="collection_id", match=models.MatchValue(value=str(collection_id))
        )
    ]

    should_conditions = []
    if keywords:
        for kw in keywords:
            should_conditions.extend(
                models.FieldCondition(key="text", match=models.MatchText(text=kw))
            )

    query_filter = models.Filter(must=must_conditions) if must_conditions else None
    query_filter.should = should_conditions

    async with config.get_qdrant_client() as client:
        search_result = await client.search(
            collection_name=config.qdrant_collection_name,
            query_vector=("text_dense", query_vector),
            limit=10,
            query_filter=query_filter,
            with_payload=True,
        )

    documents = []
    for point in search_result:
        result_dict = {
            "id": point.id,
            "score": point.score,
            "payload": point.payload,
        }
        document = _qdrant_result_to_document(result_dict)
        documents.append(document)

    build_document_for_collection = partial(build_document, session=session)

    return list(map(build_document_for_collection, documents))

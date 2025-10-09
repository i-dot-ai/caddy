from functools import partial
from typing import Any
from uuid import UUID

from langchain_core.documents import Document
from qdrant_client import models
from qdrant_client.http.models import QueryResponse, SparseVector
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
        s3_client = config.get_file_store_client()

        s3_url = s3_client.download_object_url(
            f"{resource.collection_id}/{resource.id}/{resource.filename}",
            expiration=3600,
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
    dense_query_vector = config.embedding_model.embed_documents([query])[0]
    sparse_embedder = config.get_embedding_handler()
    sparse_query_vector = list(sparse_embedder.embed(query))[0]

    must_conditions = [
        models.FieldCondition(
            key="collection_id", match=models.MatchValue(value=str(collection_id))
        )
    ]

    should_conditions = []
    if keywords:
        for kw in keywords:
            should_conditions.append(
                models.FieldCondition(key="text", match=models.MatchText(text=kw))
            )

    query_filter = models.Filter(
        must=must_conditions if must_conditions else None,
        should=should_conditions if should_conditions else None,
    )
    client = await config.get_qdrant_client()
    search_result: QueryResponse = await client.query_points(
        collection_name=config.qdrant_collection_name,
        prefetch=[
            models.Prefetch(
                query=dense_query_vector,
                using="text_dense",
                filter=query_filter,
            ),
            models.Prefetch(
                query=SparseVector(
                    indices=sparse_query_vector.indices,
                    values=sparse_query_vector.values,
                ),
                using="text_sparse",
                filter=query_filter,
            ),
        ],
        query=models.FusionQuery(
            fusion=models.Fusion.RRF,
        ),
        score_threshold=None,
        with_payload=True,
    )

    documents = []
    for point in search_result.points:
        result_dict = {
            "id": point.id,
            "score": point.score,
            "payload": point.payload,
        }
        document = _qdrant_result_to_document(result_dict)
        documents.append(document)

    build_document_for_collection = partial(build_document, session=session)

    return list(map(build_document_for_collection, documents))

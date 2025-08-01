from functools import partial
from uuid import UUID

from langchain_community.vectorstores.opensearch_vector_search import HYBRID_SEARCH
from langchain_core.documents import Document
from sqlmodel import Session

from api.environment import config
from api.models import Resource


def build_document(document: Document, collection_id, session):
    resource = session.get(Resource, document.metadata["resource_id"])

    if resource.url:
        document.metadata["url"] = resource.url
    else:
        url = config.resource_url_template.format(
            collection_id=collection_id, resource_id=resource.id
        )
        document.metadata["url"] = url

    return document


async def search_collection(
    collection_id: UUID,
    query: str,
    session: Session,
    keywords: list[str] | None = None,
) -> list[Document]:
    """Query opensearch.

    Args:
        - query (str): The query text
        - keywords: list(str):
            - Extract 3-5 specific terms that capture key issues or needs
            - Include amounts, dates, or specific services mentioned
            - Focus on actionable terms that could help find relevant documents
            - Avoid generic words or category names

    Returns:
        Documents: relevant documents
    """

    pre_filter = {"match": {"metadata.collection_id.keyword": str(collection_id)}}
    if keywords:
        pre_filter["match"]["text"] = {"query": "\n".join(keywords)}

    vector_store = config.get_vector_store()
    results = vector_store.similarity_search(
        query=query,
        k=10,
        search_type=HYBRID_SEARCH,
        search_pipeline=config.opensearch_url_pipeline,
        post_filter=pre_filter,
    )

    build_document_for_collection = partial(
        build_document, collection_id=collection_id, session=session
    )

    return list(map(build_document_for_collection, results))

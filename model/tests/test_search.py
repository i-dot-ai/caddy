from langchain_core.documents import Document

from api.search import build_document


def test_document_url(database_transaction, web_resource, example_collection):
    document_with_url = Document(
        page_content="Whatever",
        metadata={
            "resource_id": str(web_resource.id),
        },
    )

    result = build_document(
        document=document_with_url,
        session=database_transaction,
    )

    assert result.metadata.get("url") == web_resource.url

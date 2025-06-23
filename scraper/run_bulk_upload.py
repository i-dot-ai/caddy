import asyncio

from opensearch_document_manager import OpenSearchDocumentManager

from os_tools import get_os_client


for dataset in ["defra_grants", "co_grants_evaluation_reports"]:
    os_manager = OpenSearchDocumentManager(get_os_client(), index_name=dataset)
    os_manager.create_index()
    asyncio.run(os_manager.async_bulk_upload(dataset, domain=dataset))

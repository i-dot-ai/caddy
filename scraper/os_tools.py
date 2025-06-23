import os

from dotenv import load_dotenv
from opensearchpy import OpenSearch, RequestsHttpConnection


load_dotenv()
OPENSEARCH_URL = os.environ["OPENSEARCH_URL"]
SECURE = OPENSEARCH_URL != "localhost"


def get_os_client():
    return OpenSearch(
        hosts=[{"host": OPENSEARCH_URL, "port": os.environ["OPENSEARCH_PORT"]}],
        http_auth=(
            os.environ["OPENSEARCH_USER"],
            os.environ["OPENSEARCH_PASSWORD"],
        ),
        use_ssl=SECURE,
        verify_certs=SECURE,
        connection_class=RequestsHttpConnection,
        timeout=30,
    )

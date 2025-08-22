import os

import boto3
from botocore.client import Config
from opensearchpy import RequestsHttpConnection

from api.config import CaddyConfig
from api.embedding_models import load_embedding_model

embedding_model = load_embedding_model(os.environ["EMBEDDING_MODEL"])

opensearch_kwargs = {
    "hosts": [
        {"host": os.environ["OPENSEARCH_URL"], "port": os.environ["OPENSEARCH_PORT"]}
    ],
    "http_auth": (os.environ["OPENSEARCH_USER"], os.environ["OPENSEARCH_PASSWORD"]),
    "connection_class": RequestsHttpConnection,
    "timeout": 30,
    "use_ssl": False,
    "verify_certs": False,
    "scheme": "http",
}

sqlalchemy_url = "postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DB}".format(
    **os.environ
)

s3_client = boto3.client(
    "s3",
    endpoint_url=os.environ["S3_URL"],
    aws_access_key_id="minioadmin",
    aws_secret_access_key="minioadmin",  # pragma: allowlist secret
    config=Config(signature_version="s3v4"),
)

data_s3_bucket = os.environ["DATA_S3_BUCKET"]


resource_url_template = "http://localhost:8000/collections/{collection_id}/resources/{resource_id}/documents"

config = CaddyConfig(
    opensearch_kwargs=opensearch_kwargs,
    embedding_model=embedding_model,
    sqlalchemy_url=sqlalchemy_url,
    s3_client=s3_client,
    data_s3_bucket=data_s3_bucket,
    resource_url_template=resource_url_template,
    env="local",
    app_name="caddy",
    auth_provider_public_key="None",
    oidc_issuer=os.environ.get("OIDC_ISSUER"),
    oidc_audience=os.environ.get("OIDC_AUDIENCE"),
    git_sha="local",
)

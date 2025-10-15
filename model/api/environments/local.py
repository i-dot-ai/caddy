import json
import os

import boto3
from botocore.client import Config

from api.config import CaddyConfig
from api.embedding_models import load_embedding_model

embedding_model = load_embedding_model(os.environ["EMBEDDING_MODEL"])

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

keycloak_allowed_roles = json.loads(os.environ["KEYCLOAK_ALLOWED_ROLES"])

resource_url_template = "http://localhost:8000/collections/{collection_id}/resources/{resource_id}/documents"

qdrant__service__api_key = os.environ["QDRANT__SERVICE__API_KEY"]
qdrant_url = os.environ["QDRANT_URL"]

config = CaddyConfig(
    qdrant__service__api_key=qdrant__service__api_key,
    qdrant_url=qdrant_url,
    embedding_model=embedding_model,
    sqlalchemy_url=sqlalchemy_url,
    s3_client=s3_client,
    data_s3_bucket=data_s3_bucket,
    resource_url_template=resource_url_template,
    env="local",
    app_name="caddy",
    disable_auth_signature_verification=True,
    auth_provider_public_key="None",
    keycloak_allowed_roles=keycloak_allowed_roles,
    git_sha="local",
)

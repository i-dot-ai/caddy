import json
import os

import boto3
from requests_aws4auth import AWS4Auth

from api.config import CaddyConfig
from api.embedding_models import load_embedding_model

embedding_model = load_embedding_model(os.environ["EMBEDDING_MODEL"])

disable_auth_signature_verification = os.environ["DISABLE_AUTH_SIGNATURE_VERIFICATION"]
auth_provider_public_key = os.environ["AUTH_PROVIDER_PUBLIC_KEY"]
sentry_dsn = os.environ["SENTRY_DSN"]

session = boto3.Session(region_name=os.environ["OPENSEARCH_AWS_REGION"])
credentials = session.get_credentials()
auth = AWS4Auth(
    region=os.environ["OPENSEARCH_AWS_REGION"],
    service="es",
    refreshable_credentials=credentials,
)

sqlalchemy_url = "postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DB}".format(
    **os.environ
)

s3_client = boto3.client("s3")

data_s3_bucket = os.environ["DATA_S3_BUCKET"]

keycloak_allowed_roles = json.loads(os.environ["KEYCLOAK_ALLOWED_ROLES"])

environment = os.environ["ENVIRONMENT"]

resource_url_template = os.environ["RESOURCE_URL_TEMPLATE"]

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
    env=environment,
    app_name="caddy",
    disable_auth_signature_verification=disable_auth_signature_verification,
    auth_provider_public_key=auth_provider_public_key,
    sentry_dsn=sentry_dsn,
    keycloak_allowed_roles=keycloak_allowed_roles,
    git_sha=os.getenv("GIT_SHA"),
)

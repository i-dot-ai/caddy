import json
import os

import boto3
from opensearchpy import RequestsHttpConnection
from requests_aws4auth import AWS4Auth

from api.config import CaddyConfig
from api.embedding_models import load_embedding_model

embedding_model = load_embedding_model(os.environ["EMBEDDING_MODEL"])

disable_auth_signature_verification = os.environ["DISABLE_AUTH_SIGNATURE_VERIFICATION"]
auth_provider_public_key = os.environ["AUTH_PROVIDER_PUBLIC_KEY"]
oidc_issuer = os.environ.get("OIDC_ISSUER")
oidc_audience = os.environ.get("OIDC_AUDIENCE")
sentry_dsn = os.environ["SENTRY_DSN"]

session = boto3.Session(region_name=os.environ["OPENSEARCH_AWS_REGION"])
credentials = session.get_credentials()
auth = AWS4Auth(
    region=os.environ["OPENSEARCH_AWS_REGION"],
    service="es",
    refreshable_credentials=credentials,
)

opensearch_kwargs = {
    "hosts": [
        {"host": os.environ["OPENSEARCH_URL"], "port": os.environ["OPENSEARCH_PORT"]}
    ],
    "http_auth": auth,
    "region": os.environ["OPENSEARCH_AWS_REGION"],
    "connection_class": RequestsHttpConnection,
    "timeout": 30,
    "use_ssl": True,
    "verify_certs": True,
    "scheme": "https",
}

sqlalchemy_url = "postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DB}".format(
    **os.environ
)

s3_client = boto3.client("s3")

data_s3_bucket = os.environ["DATA_S3_BUCKET"]


environment = os.environ["ENVIRONMENT"]

resource_url_template = os.environ["RESOURCE_URL_TEMPLATE"]

config = CaddyConfig(
    opensearch_kwargs=opensearch_kwargs,
    embedding_model=embedding_model,
    sqlalchemy_url=sqlalchemy_url,
    s3_client=s3_client,
    data_s3_bucket=data_s3_bucket,
    resource_url_template=resource_url_template,
    env=environment,
    app_name="caddy",
    disable_auth_signature_verification=disable_auth_signature_verification,
    auth_provider_public_key=auth_provider_public_key,
    oidc_issuer=oidc_issuer,
    oidc_audience=oidc_audience,
    sentry_dsn=sentry_dsn,
    git_sha=os.getenv("GIT_SHA"),
)

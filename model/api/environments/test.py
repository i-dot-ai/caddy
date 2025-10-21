import json
import os

from api.config import CaddyConfig

disable_auth_signature_verification = os.environ["DISABLE_AUTH_SIGNATURE_VERIFICATION"]
auth_provider_public_key = os.environ["AUTH_PROVIDER_PUBLIC_KEY"]

sqlalchemy_url = "postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DB}".format(
    **os.environ
)

data_s3_bucket = "test-bucket"

keycloak_allowed_roles = json.loads(os.environ["KEYCLOAK_ALLOWED_ROLES"])

resource_url_template = "http://localhost:8000/collections/{collection_id}/resources/{resource_id}/documents"


qdrant__service__api_key = os.environ.get("QDRANT__SERVICE__API_KEY", None)
qdrant_url = os.environ["QDRANT_URL"]
qdrant_collection_name = os.environ["QDRANT_COLLECTION_NAME"]

config = CaddyConfig(
    qdrant__service__api_key=qdrant__service__api_key,
    qdrant_url=qdrant_url,
    qdrant_collection_name=qdrant_collection_name,
    sqlalchemy_url=sqlalchemy_url,
    data_s3_bucket=data_s3_bucket,
    resource_url_template=resource_url_template,
    env="test",
    app_name="caddy_model",
    disable_auth_signature_verification=disable_auth_signature_verification,
    auth_provider_public_key=auth_provider_public_key,
    keycloak_allowed_roles=keycloak_allowed_roles,
    git_sha=os.getenv("GIT_SHA", "test"),  # tests can override if they want
)

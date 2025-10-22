import json
import os

from api.environments.config import CaddyConfig

sqlalchemy_url = "postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DB}".format(
    **os.environ
)

data_s3_bucket = os.environ["IAI_FS_BUCKET_NAME"]

keycloak_allowed_roles = json.loads(os.environ["KEYCLOAK_ALLOWED_ROLES"])

resource_url_template = "http://localhost:8000/collections/{collection_id}/resources/{resource_id}/documents"

qdrant__service__api_key = os.environ["QDRANT__SERVICE__API_KEY"]
qdrant_url = os.environ["QDRANT_URL"]

config = CaddyConfig(
    qdrant__service__api_key=qdrant__service__api_key,
    qdrant_url=qdrant_url,
    sqlalchemy_url=sqlalchemy_url,
    data_s3_bucket=data_s3_bucket,
    resource_url_template=resource_url_template,
    env="local",
    app_name="caddy",
    disable_auth_signature_verification=True,
    auth_provider_public_key="None",
    keycloak_allowed_roles=keycloak_allowed_roles,
    git_sha="local",
)

import os

from i_dot_ai_utilities.logging.structured_logger import StructuredLogger
from i_dot_ai_utilities.logging.types.enrichment_types import ExecutionEnvironmentType
from i_dot_ai_utilities.logging.types.log_output_format import LogOutputFormat
from i_dot_ai_utilities.metrics.cloudwatch import CloudwatchEmbeddedMetricsWriter
from langchain_community.vectorstores import OpenSearchVectorSearch
from opensearchpy import NotFoundError, OpenSearch
from sqlmodel import create_engine

EMBEDDING_DIMENSION = 1024


class CaddyConfig:
    def __init__(
        self,
        opensearch_kwargs,
        embedding_model,
        sqlalchemy_url: str,
        s3_client,
        data_s3_bucket: str,
        resource_url_template: str,
        opensearch_url_pipeline="hybrid_search_pipeline",
        env="local",
        app_name="caddy_model",
        backend_host="http://localhost:8000",
        disable_auth_signature_verification=False,
        auth_provider_public_key="none",
        sentry_dsn=None,
        s3_prefix="app_data",
        keycloak_allowed_roles=None,
        git_sha=None,
    ):
        self.opensearch_kwargs = opensearch_kwargs
        self.opensearch_url_pipeline = opensearch_url_pipeline
        self.embedding_model = embedding_model
        self.env = env.upper()
        self.sentry_dsn = sentry_dsn
        self.app_name = app_name
        self.disable_auth_signature_verification = disable_auth_signature_verification
        self.auth_provider_public_key = auth_provider_public_key
        self.sqlalchemy_url = sqlalchemy_url
        self.keycloak_allowed_roles = keycloak_allowed_roles or []
        self.s3_client = s3_client
        self.data_s3_bucket = data_s3_bucket
        self.s3_prefix = s3_prefix
        self.resource_url_template = resource_url_template
        self.git_sha = git_sha
        self.admin_users = os.environ.get("ADMIN_USERS", "").split(",")
        self.backend_host = backend_host

        self.os_index_name = (
            "caddy_text_chunks_test" if self.env == "TEST" else "caddy_text_chunks"
        )

        if self.env not in ("PROD", "PREPROD", "DEV"):
            if not any(
                bucket["Name"] == self.data_s3_bucket
                for bucket in self.s3_client.list_buckets()["Buckets"]
            ):
                self.s3_client.create_bucket(Bucket=self.data_s3_bucket)

        self._init_vector_store()

    def get_os_client(self):
        return OpenSearch(**self.opensearch_kwargs)

    def get_vector_store(self):
        # langchain insists on a URL param even though it's also defined in "hosts"
        opensearch_url = "{}://{}:{}".format(
            self.opensearch_kwargs["scheme"],
            self.opensearch_kwargs["hosts"][0]["host"],
            self.opensearch_kwargs["hosts"][0]["port"],
        )
        new_kwargs = {k: v for k, v in self.opensearch_kwargs.items() if k != "hosts"}

        return OpenSearchVectorSearch(
            opensearch_url,
            index_name=self.os_index_name,
            embedding_function=self.embedding_model,
            **new_kwargs,
        )

    def _init_vector_store(self):
        vector_store = self.get_vector_store()
        if not vector_store.index_exists(self.os_index_name):
            vector_store.create_index(
                EMBEDDING_DIMENSION, self.os_index_name, engine="faiss"
            )
        try:
            vector_store.client.transport.perform_request(
                method="GET", url=f"/_search/pipeline/{self.opensearch_url_pipeline}"
            )
        except NotFoundError:
            vector_store.configure_search_pipelines(
                self.opensearch_url_pipeline, 0.3, 0.7
            )
        return vector_store

    def get_database(self):
        return create_engine(self.sqlalchemy_url)

    def get_logger(self, name: str) -> StructuredLogger:
        logger_environment = (
            ExecutionEnvironmentType.LOCAL
            if self.env.upper() in ["LOCAL", "TEST"]
            else ExecutionEnvironmentType.FARGATE
        )
        logger_format = (
            LogOutputFormat.TEXT
            if self.env.upper() in ["LOCAL", "TEST"]
            else LogOutputFormat.JSON
        )

        logger = StructuredLogger(
            level="info",
            options={
                "execution_environment": logger_environment,
                "log_format": logger_format,
                "logger_name": name,
            },
        )
        return logger

    def get_metrics_writer(self) -> CloudwatchEmbeddedMetricsWriter:
        return CloudwatchEmbeddedMetricsWriter(
            namespace=self.app_name,
            environment=self.env,
            logger=self.get_logger(__name__),
        )

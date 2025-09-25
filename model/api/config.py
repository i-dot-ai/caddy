import os
from contextlib import contextmanager
from functools import lru_cache

from fastembed import SparseTextEmbedding
from i_dot_ai_utilities.logging.structured_logger import StructuredLogger
from i_dot_ai_utilities.logging.types.enrichment_types import ExecutionEnvironmentType
from i_dot_ai_utilities.logging.types.log_output_format import LogOutputFormat
from i_dot_ai_utilities.metrics.cloudwatch import CloudwatchEmbeddedMetricsWriter
from qdrant_client import AsyncQdrantClient, QdrantClient, models
from qdrant_client.http.models import TextIndexType
from sqlmodel import create_engine

EMBEDDING_DIMENSION = 1024


class CaddyConfig:
    def __init__(
        self,
        embedding_model,
        sqlalchemy_url: str,
        s3_client,
        data_s3_bucket: str,
        resource_url_template: str,
        qdrant_url: str,
        qdrant__service__api_key: str,
        qdrant_collection_name: str = "caddy_collection",
        env="local",
        app_name="caddy_model",
        disable_auth_signature_verification=False,
        auth_provider_public_key="none",
        sentry_dsn=None,
        s3_prefix="app_data",
        keycloak_allowed_roles=None,
        git_sha=None,
    ):
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
        self.qdrant_url = qdrant_url
        self.qdrant__service__api_key = qdrant__service__api_key
        self.qdrant_collection_name = qdrant_collection_name

        if self.env not in ("PROD", "PREPROD", "DEV"):
            if not any(
                bucket["Name"] == self.data_s3_bucket
                for bucket in self.s3_client.list_buckets()["Buckets"]
            ):
                self.s3_client.create_bucket(Bucket=self.data_s3_bucket)

        self._qdrant_client: AsyncQdrantClient | None = None

    async def get_qdrant_client(self) -> AsyncQdrantClient:
        """Get or create a persistent Qdrant client."""
        if self._qdrant_client is None:
            self._qdrant_client = AsyncQdrantClient(
                url=self.qdrant_url,
                api_key=self.qdrant__service__api_key,
                timeout=60,
            )
        return self._qdrant_client

    async def close_qdrant_client(self):
        """Clean up Qdrant client on shutdown."""
        if self._qdrant_client:
            await self._qdrant_client.close()
            self._qdrant_client = None

    @contextmanager
    def get_sync_qdrant_client(self) -> QdrantClient:
        """Gets a sync Qdrant client from environment variables.

        Supports both cloud (via API key) and local connections.
        """
        logger = self.get_logger(__name__)
        logger.info("Connecting to Qdrant at {qdrant_url}", qdrant_url=self.qdrant_url)
        client = QdrantClient(
            url=self.qdrant_url, api_key=self.qdrant__service__api_key, timeout=30
        )

        try:
            yield client
        finally:
            client.close()

    async def initialize_qdrant_collections(self) -> None:
        """Initialize Qdrant with proper collections.

        This function abstracts the common initialization logic used by both
        the CLI and test fixtures.
        """
        # Create collections with appropriate vector dimensions
        await self._create_collection_if_none()

    async def _collection_exists(self, collection_name: str) -> bool:
        """Checks if a collection exists in Qdrant."""
        client = await self.get_qdrant_client()
        return await client.collection_exists(collection_name)

    async def _create_collection_if_none(self) -> None:
        """Create Qdrant collection if it doesn't exist."""
        distance = models.Distance.DOT
        logger = self.get_logger(__name__)
        client = await self.get_qdrant_client()
        if not await self._collection_exists(self.qdrant_collection_name):
            await client.create_collection(
                collection_name=self.qdrant_collection_name,
                vectors_config={
                    "text_dense": models.VectorParams(
                        size=1024,
                        distance=distance,
                    ),
                },
                sparse_vectors_config={
                    "text_sparse": models.SparseVectorParams(
                        index=models.SparseIndexParams(),
                        modifier=models.Modifier.IDF,
                    ),
                },
                quantization_config=models.ScalarQuantization(
                    scalar=models.ScalarQuantizationConfig(
                        type=models.ScalarType.INT8,
                        always_ram=True,
                    )
                ),
            )

            # Add index for text search
            await client.create_payload_index(
                collection_name=self.qdrant_collection_name,
                field_name="text",
                field_schema=models.TextIndexParams(
                    type=TextIndexType.TEXT,
                    tokenizer=models.TokenizerType.WORD,
                    stemmer=models.SnowballParams(
                        type=models.Snowball.SNOWBALL,
                        language=models.SnowballLanguage.ENGLISH,
                    ),
                    stopwords=models.StopwordsSet(
                        languages=[
                            models.Language.ENGLISH,
                        ],
                    ),
                    min_token_len=2,
                    max_token_len=10,
                    lowercase=True,
                ),
            )

            # Add indexes for collection, resource and chunk IDs
            await client.create_payload_index(
                collection_name=self.qdrant_collection_name,
                field_name="collection_id",
                field_schema="keyword",
            )
            await client.create_payload_index(
                collection_name=self.qdrant_collection_name,
                field_name="resource_id",
                field_schema="keyword",
            )
            await client.create_payload_index(
                collection_name=self.qdrant_collection_name,
                field_name="chunk_id",
                field_schema="keyword",
            )

            logger.info(
                "Created collection and indexes for - {collection_name}",
                collection_name=self.qdrant_collection_name,
            )
        else:
            logger.info(
                "Collection already exists - {collection_name}",
                collection_name=self.qdrant_collection_name,
            )

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

    @staticmethod
    @lru_cache
    def get_embedding_handler() -> SparseTextEmbedding:
        # Using the following embedding model because it has a defined vocabulary size
        return SparseTextEmbedding(model_name="Qdrant/bm42-all-minilm-l6-v2-attentions")

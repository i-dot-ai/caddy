import os.path
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pytest_postgresql.janitor import DatabaseJanitor
from sqlmodel import Session

from alembic import command
from alembic.config import Config
from api.app import app
from api.config import EMBEDDING_DIMENSION
from api.environment import config, get_session
from api.mcp_app import session_manager
from api.models import (
    Collection,
    Resource,
    Role,
    TextChunk,
    User,
    UserCollection,
)

CWD = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(autouse=True)
def cleanup_opensearch_per_test():
    """Clean up OpenSearch documents after each test"""
    yield
    # Delete all documents from the test index
    config.get_os_client().delete_by_query(
        index=config.os_index_name, body={"query": {"match_all": {}}}, refresh=True
    )


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    janitor = DatabaseJanitor(
        # we have to pass these separately unf
        user=os.environ.get("POSTGRES_USER"),
        password=os.environ.get("POSTGRES_PASSWORD"),
        host=os.environ.get("POSTGRES_HOST"),
        port=os.environ.get("POSTGRES_PORT"),
        dbname=os.environ.get("POSTGRES_DB"),
        version=16,
    )
    try:
        janitor.drop()
    except Exception:
        pass  # we don't care if db isn't there to drop
    finally:
        janitor.init()  # create the db

    # Migrate
    alembic_cfg = Config(os.path.join(CWD, "..", "alembic.ini"))
    command.upgrade(alembic_cfg, "head")


@pytest.fixture(scope="function", autouse=True)
def database_transaction():
    engine = config.get_database()
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    try:
        # this is a bit jank but it seems to work: re-patch
        # per test run with a connection wrapped in a transaction
        # this is needed for the MCP tooling which doesnt support dependency injection
        with patch("api.environment.config.get_database", return_value=session.bind):
            yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(name="client")
def client_fixture(database_transaction):
    def _get_session():
        return database_transaction

    app.dependency_overrides[get_session] = _get_session

    client = TestClient(app)
    yield client


@pytest.fixture
def example_collection(database_transaction):
    collection_db = Collection(name="my-collection", description="a collection")
    database_transaction.add(collection_db)
    database_transaction.commit()
    database_transaction.refresh(collection_db)
    yield collection_db


@pytest.fixture
def another_example_collection(database_transaction):
    collection_db = Collection(
        name="another-collection", description="another collection"
    )
    database_transaction.add(collection_db)
    database_transaction.commit()
    database_transaction.refresh(collection_db)
    yield collection_db


@pytest.fixture
def web_resource(database_transaction, example_collection):
    web_resource = Resource(
        collection_id=example_collection.id,
        filename="webpage.html",
        content_type="text/html",
        url="http://example.com/webpage.html",
    )

    database_transaction.add(web_resource)
    database_transaction.commit()

    return web_resource


@pytest.fixture
def example_document(database_transaction, example_collection, normal_user):
    gov_uk_resource = Resource(
        collection_id=example_collection.id,
        created_by_id=normal_user.id,
        filename="gov.pdf",
        content_type="text/html",
    )

    text_chunk = TextChunk(
        resource=gov_uk_resource,
        text="The best place to find government services and information",
        embedding=list(range(EMBEDDING_DIMENSION)),
        order=1,
    )

    database_transaction.add(gov_uk_resource)
    database_transaction.add(text_chunk)
    database_transaction.commit()
    yield text_chunk


@pytest.fixture
def another_example_document(database_transaction, another_example_collection):
    resource = Resource(
        collection_id=another_example_collection.id,
        filename="gov.pdf",
        content_type="text/html",
    )

    text_chunk = TextChunk(
        resource=resource,
        text="The best place to find government services and information",
        embedding=list(range(EMBEDDING_DIMENSION)),
        order=1,
    )

    database_transaction.add(resource)
    database_transaction.add(text_chunk)
    database_transaction.commit()
    yield text_chunk


@pytest.fixture
def many_documents(
    example_collection: Collection,
    database_transaction,
    normal_user,
):
    # 50 resources with 10 documents each
    resources = []
    text_chunks = []

    for i in range(50):
        filename = str(i).rjust(2, "0")
        r = Resource(
            id=UUID(str(i).rjust(32, "0")),
            collection_id=example_collection.id,
            created_by_id=normal_user.id,
            filename=f"filename-{filename}",
            content_type="text/plain",
            created_at="2001-01-01T01:01:00",
        )
        database_transaction.add(r)
        resources.append(r)

        for j in range(10):
            uuid = i * 10 + j
            tc = TextChunk(
                id=str(UUID(str(uuid).rjust(32, "0"))),
                resource=r,
                text=f"resource={i}, document={j}",
                embedding=list(range(EMBEDDING_DIMENSION)),
                order=j,
                created_at="2001-01-01T01:01:00",
            )
            database_transaction.add(tc)
            text_chunks.append(tc)

    database_transaction.commit()
    yield text_chunks


@pytest.fixture()
def admin_user(database_transaction):
    user = User(email="alice@example.com", is_admin=True)
    database_transaction.add(user)
    database_transaction.commit()

    yield database_transaction.get(User, user.id)


@pytest.fixture()
def normal_user(database_transaction):
    user = User(email="bob@example.com", is_admin=False)
    database_transaction.add(user)
    database_transaction.commit()

    yield database_transaction.get(User, user.id)


@pytest.fixture()
def collection_manager(admin_user, example_collection, database_transaction):
    user_role = UserCollection(
        user_id=admin_user.id,
        collection_id=example_collection.id,
        role=Role.MANAGER,
    )
    database_transaction.add(user_role)
    database_transaction.commit()
    database_transaction.refresh(user_role)

    yield user_role


@pytest.fixture()
def collection_manager_non_admin(normal_user, example_collection, database_transaction):
    user_role = UserCollection(
        user_id=normal_user.id,
        collection_id=example_collection.id,
        role=Role.MANAGER,
    )
    database_transaction.add(user_role)
    database_transaction.commit()
    database_transaction.refresh(user_role)

    yield user_role


@pytest.fixture
def fresh_session_manager():
    """Reset the session manager state after each test."""
    yield session_manager
    with session_manager._run_lock:
        session_manager._has_started = False

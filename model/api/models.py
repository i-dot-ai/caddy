import asyncio
import threading
from datetime import datetime
from typing import Any, Self
from uuid import UUID, uuid4

import jwt
from pgvector.sqlalchemy import Vector
from pydantic import BaseModel, EmailStr
from pytz import utc
from qdrant_client.http.models import models
from sqlalchemy import event
from sqlmodel import Field, Relationship, Session, SQLModel, select

from api.config import EMBEDDING_DIMENSION
from api.environment import config
from api.types import CollectionBase, PaginatedResponse, ResourceBase, Role


def user_token(user):
    """
    Return a dummy JWT from cognito to allow for local testing.
    """
    jwt_dict = {
        "sub": "90429234-4031-7077-b9ba-60d1af121245",
        "email": user.email,
        "aud": "account",
        "exp": 1727262399,
        "realm_access": {"roles": []},
        "resource_access": {"account": {"roles": ["view-profile"]}},
    }
    jwt_headers = {
        "typ": "JWT",
        "kid": "1234947a-59d3-467c-880c-f005c6941ffg",
        "alg": "HS256",
        "iss": "https://keycloak-dev.ai.cabinetoffice.gov.uk/realms/i_ai",
        "client": "323jd0nindova3squ5ln665432",
        "signer": "arn:aws:elasticloadbalancing:eu-west-2:acc:loadbalancer/app/alb/99jd250a03e75des",
        "exp": 1727262399,
    }
    return f"Bearer {jwt.encode(jwt_dict, "secret", algorithm="HS256", headers=jwt_headers)}"


def utc_now() -> datetime:
    return datetime.now(tz=utc)


class User(SQLModel, table=True):
    id: UUID = Field(primary_key=True, default_factory=uuid4)
    email: EmailStr = Field(description="user email", unique=True)
    created_at: datetime = Field(default_factory=utc_now)
    is_admin: bool = Field(description="is this user an administrator", default=False)

    @classmethod
    def get_by_email(cls, session: Session, email: EmailStr) -> Self | None:
        statement = select(cls).where(cls.email == email)
        return session.exec(statement).one_or_none()

    @property
    def token(self):
        return user_token(self)

    def __str__(self):
        return self.email.lower()


class Collection(CollectionBase, SQLModel, table=True):
    id: UUID = Field(
        primary_key=True, description="id for collection", default_factory=uuid4
    )
    created_at: datetime | None = Field(default_factory=utc_now)


class UserCollection(SQLModel, table=True):
    user_id: UUID = Field(foreign_key="user.id", primary_key=True, ondelete="CASCADE")
    user: User = Relationship()

    collection_id: UUID = Field(
        foreign_key="collection.id", primary_key=True, ondelete="CASCADE"
    )
    collection: Collection = Relationship()

    role: Role = Field(
        description="role that the user can have for this collection",
        default=Role.MEMBER,
    )
    created_at: datetime = Field(default_factory=utc_now)


class Resource(ResourceBase, SQLModel, table=True):
    id: UUID = Field(primary_key=True, default_factory=uuid4)
    created_at: datetime = Field(
        description="timestamp at which this resource was ingested into Caddy",
        default_factory=utc_now,
    )
    created_by_id: UUID | None = Field(
        foreign_key="user.id", default=None, ondelete="SET NULL"
    )
    created_by: User = Relationship()
    collection_id: UUID = Field(
        foreign_key="collection.id", ondelete="CASCADE", index=True
    )


class TextChunk(SQLModel, table=True):
    id: UUID = Field(primary_key=True, default_factory=uuid4)
    created_at: datetime = Field(
        description="timestamp at which this chunk was ingested into Caddy",
        default_factory=utc_now,
    )
    resource_id: UUID = Field(foreign_key="resource.id", ondelete="CASCADE", index=True)
    resource: Resource = Relationship()

    text: str = Field(description="text extracted from file")
    embedding: Any = Field(sa_type=Vector(EMBEDDING_DIMENSION))
    order: int = Field(description="extraction order of text-chunk")


class UserCollectionWithEmail(BaseModel):
    user_id: UUID
    collection_id: UUID
    user_email: EmailStr
    role: Role = Field(default=Role.MEMBER)
    created_at: datetime = Field(default_factory=utc_now)


class UserRoleList(PaginatedResponse):
    user_roles: list[UserCollectionWithEmail] | None = None


def index_document(mapper, connection, target: TextChunk):
    """Index a document in Qdrant when a TextChunk is added to the database."""
    if _is_in_pytest():
        thread = threading.Thread(target=_sync_index_document, args=(target,))
        thread.start()
        thread.join()
    else:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_async_index_document(target))
        except RuntimeError:
            asyncio.run(_async_index_document(target))


def delete_document(mapper, connection, target: Resource):
    """Delete documents from Qdrant when a Resource is removed from the database."""
    if _is_in_pytest():
        thread = threading.Thread(target=_sync_delete_document, args=(target,))
        thread.start()
        thread.join()
    else:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_async_delete_document(target))
        except RuntimeError:
            asyncio.run(_async_delete_document(target))


def delete_chunk_document(mapper, connection, target: TextChunk):
    """Delete documents from Qdrant when a TextChunk is removed from the database."""
    if _is_in_pytest():
        thread = threading.Thread(target=_sync_delete_document, args=(target.resource,))
        thread.start()
        thread.join()
    else:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_async_delete_document(target.resource))
        except RuntimeError:
            asyncio.run(_async_delete_document(target.resource))


def _is_in_pytest():
    """Check if app is doing tests"""
    return config.env.lower() == "test"


def _sync_index_document(target):
    """Sync wrapper for async index operation."""
    asyncio.run(_async_index_document(target))


def _sync_delete_document(target):
    """Sync wrapper for async delete operation."""
    asyncio.run(_async_delete_document(target))


async def _async_index_document(target: TextChunk):
    """Async helper to index a document in Qdrant."""
    async with config.get_qdrant_client() as client:
        point = models.PointStruct(
            id=str(target.id),
            vector={
                "text_dense": target.embedding,
            },
            payload={
                "text": target.text,
                "created_at": target.resource.created_at.isoformat()
                if isinstance(target.resource.created_at, datetime)
                else target.resource.created_at,
                "filename": target.resource.filename,
                "content_type": target.resource.content_type,
                "resource_id": str(target.resource.id),
                "collection_id": str(target.resource.collection_id),
            },
        )

        await client.upsert(
            collection_name=config.qdrant_collection_name, points=[point]
        )


async def _async_delete_document(target: Resource):
    """Async helper to delete a single document from Qdrant."""
    async with config.get_qdrant_client() as client:
        await client.delete(
            collection_name=config.qdrant_collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="resource_id",
                            match=models.MatchValue(value=str(target.id)),
                        )
                    ]
                )
            ),
        )


# Register SQLAlchemy events
# Cascade deletions don't trigger these hooks when a Resource is deleted
# So separate deletion hooks are required for TextChunk and Resource
event.listen(TextChunk, "after_insert", index_document)
event.listen(Resource, "after_delete", delete_document)
event.listen(TextChunk, "after_delete", delete_chunk_document)

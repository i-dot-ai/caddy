import os
from datetime import datetime
from typing import Any, Self
from uuid import UUID, uuid4

import requests
from pgvector.sqlalchemy import Vector
from pydantic import BaseModel, EmailStr
from pytz import utc
from sqlalchemy import event
from sqlmodel import Field, Relationship, Session, SQLModel, select

from api.config import EMBEDDING_DIMENSION
from api.environment import config
from api.types import CollectionBase, PaginatedResponse, ResourceBase, Role


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
        token_url = os.environ["OIDC_ISSUER"] + "/token"
        data = {
            "grant_type": "password",
            "client_id": os.environ["OIDC_AUDIENCE"],
            "client_secret": os.environ["OAUTH2_CLIENT_SECRET"],
            "username": self.email,
            "password": "password",  # pragma: allowlist secret
            "scope": "openid email profile",
        }
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        return response.json()["access_token"]

    def __str__(self):
        return self.email


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


class ResourceVersion(SQLModel, table=True):
    id: UUID = Field(primary_key=True, default_factory=uuid4)
    created_at: datetime = Field(
        description="timestamp at which this resource was ingested into Caddy",
        default_factory=utc_now,
    )
    created_by_id: UUID | None = Field(
        foreign_key="user.id", default=None, ondelete="SET NULL"
    )
    created_by: User = Relationship()
    text: str = Field(description="text extracted from file")
    resource_id: UUID = Field(foreign_key="resource.id", ondelete="CASCADE", index=True)
    resource: Resource = Relationship()


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


# OpenSearch sync functions
def index_document(mapper, connection, target: TextChunk):
    doc = {
        "vector_field": target.embedding,
        "text": target.text,
        "metadata": {
            "created_at": target.resource.created_at,
            "filename": target.resource.filename,
            "content_type": target.resource.content_type,
            "resource_id": str(target.resource.id),
            "collection_id": str(target.resource.collection_id),
        },
    }
    config.get_os_client().index(
        index=config.os_index_name,
        id=target.id,
        body=doc,
        refresh=config.env == "TEST",
    )


def delete_document(mapper, connection, target: TextChunk):
    config.get_os_client().delete_by_query(
        index=config.os_index_name,
        body={
            "query": {
                "term",
                {"metadata.collection_id.keyword": str(target.resource.collection_id)},
            }
        },
    )


# Register SQLAlchemy events
event.listen(TextChunk, "after_insert", index_document)
event.listen(TextChunk, "after_delete", delete_document)

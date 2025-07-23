import enum
from datetime import datetime, timedelta
from uuid import UUID

from langchain_core.documents import Document
from pydantic import BaseModel, EmailStr, Field

from api.enums import CollectionPermissionEnum, ResourcePermissionEnum


class QueryRequest(BaseModel):
    query: str
    collection_name: str = Field(alias="index_name")


class CollectionBase(BaseModel):
    name: str = Field(
        description="collection name",
        pattern=r"^[\w-]+$",
        min_length=3,
        max_length=36,
        examples=["my-collection"],
    )
    description: str = Field(description="used by LLM to choose tool suitability")


class ResourceBase(BaseModel):
    filename: str | None = Field(description="name of original file")
    content_type: str | None = Field(description="type of content")
    url: str | None = Field(description="url of the uploaded resource", default=None)
    is_processed: bool = Field(
        description="has this file been processed", default=False
    )
    process_error: str | None = Field(
        description="error encountered during processing file, if any", default=None
    )
    process_time: timedelta | None = Field(
        description="time take to process file", default=None
    )


class PaginatedResponse(BaseModel):
    page: int = 1
    page_size: int = 10
    total: int


class Chunks(PaginatedResponse):
    collection_id: UUID
    resource_id: UUID
    documents: list[Document] = Field(
        description="Documents belonging to this resource", default=None
    )


class Role(enum.Enum):
    MANAGER = "manager"
    MEMBER = "member"


class UserRole(BaseModel):
    email: EmailStr = Field(description="user email", unique=True)
    role: Role = Field(
        description="role that the user can have for this collection",
        default=Role.MEMBER,
    )


class CollectionDto(CollectionBase):
    """
    Dto (Data Transfer Object) for returning supplemented collection information
    """

    id: UUID
    created_at: datetime | None = Field(
        description="collection creation date", default=None
    )
    permissions: list[CollectionPermissionEnum] = Field(
        description="Collection permission enum(s)", default_factory=list
    )


class CollectionsDto(PaginatedResponse):
    """
    Dto (Data Transfer Object) for returning supplemented collections list information
    """

    collections: list[CollectionDto] | None = None
    is_admin: bool = Field(
        description="is the current user a super admin?", default=False
    )


class ResourceDto(ResourceBase):
    id: UUID
    created_by_id: UUID
    collection_id: UUID
    created_at: datetime | None = Field(
        description="collection creation date", default=None
    )
    permissions: list[ResourcePermissionEnum] = Field(
        description="Resource permission enum(s)", default_factory=list
    )


class CollectionResources(PaginatedResponse):
    collection_id: UUID
    resources: list[ResourceDto] = Field(
        description="Resources belonging to this collection", default=None
    )

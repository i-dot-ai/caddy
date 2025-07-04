import enum
from datetime import datetime
from uuid import UUID

from langchain_core.documents import Document
from pydantic import BaseModel, EmailStr, Field


class QueryRequest(BaseModel):
    query: str
    collection_name: str = Field(alias="index_name")


class CollectionBase(BaseModel):
    name: str = Field(
        description="collection name",
        pattern=r"^[\w-]+$",
        min_length=3,
        max_length=30,
        examples=["my-collection"],
    )
    description: str = Field(description="used by LLM to choose tool suitability")


class UrlListBase(BaseModel):
    urls: list[str]


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
    is_manager: bool = Field(
        description="is manager of this collection or not", default=False
    )


class CollectionsDto(PaginatedResponse):
    """
    Dto (Data Transfer Object) for returning supplemented collections list information
    """

    collections: list[CollectionDto] | None = None
    is_admin: bool = Field(
        description="is the current user a super admin?", default=False
    )

from enum import Enum
from functools import lru_cache
from logging import getLogger

from sqlalchemy import func
from sqlmodel import Session, select

from api.environment import config
from api.models import (
    Collection,
    Resource,
    User,
    UserCollection,
)
from api.types import (
    CollectionDto,
    CollectionsDto,
    Role,
)

logger = getLogger(__name__)


@lru_cache
def get_session() -> Session:
    with Session(config.get_database()) as session:
        yield session


class NoPermissionException(Exception):
    """Exception raised for custom error in the application."""

    def __init__(self, message, error_code):
        super().__init__(message)
        self.error_code = error_code
        self.message = message

    def __str__(self):
        return f"{self.message} (Error Code: {self.error_code})"


class CollectionPermissionEnum(Enum):
    NONE = 0
    READ = 1
    WRITE = 2
    MANAGE_USERS = 3
    MANAGE_RESOURCES = 4
    ALL = 5


class ResourcePermissionEnum(Enum):
    NONE = 0
    READ = 1
    WRITE = 2
    DELETE = 3
    ALL = 4


class UserPermissions:
    def __init__(
        self,
        resource_permission: ResourcePermissionEnum,
        collection_permission: CollectionPermissionEnum,
    ):
        self.resource_permission = resource_permission
        self.collection_permission = collection_permission


def __is_user_super_admin(user: User):
    return user.email in config.SUPER_ADMINS


def __get_user_system_permissions(user: User) -> UserPermissions:
    if __is_user_super_admin(user) or user.is_admin:
        return UserPermissions(ResourcePermissionEnum.ALL, CollectionPermissionEnum.ALL)
    else:
        return UserPermissions(
            ResourcePermissionEnum.NONE, CollectionPermissionEnum.READ
        )


def __get_user_collection_permissions(
    user: User, collection: Collection, session: Session | None
) -> CollectionPermissionEnum:
    if user.is_admin or __is_user_super_admin(user):
        return CollectionPermissionEnum.ALL
    else:
        if not session:
            session = get_session()
        stmt = select(UserCollection).where(
            UserCollection.user_id == user.id
            and UserCollection.collection_id == collection.id
        )
        results = session.exec(stmt).first()
        if not results:
            return CollectionPermissionEnum.NONE
        if results.role == Role.MANAGER:
            return CollectionPermissionEnum.ALL
        if results.role == Role.MEMBER:
            return CollectionPermissionEnum.READ
    return CollectionPermissionEnum.NONE


def __get_user_resource_permissions(
    user: User, resource: Resource, session: Session | None
) -> ResourcePermissionEnum:
    if user.is_admin or __is_user_super_admin(user):
        return ResourcePermissionEnum.ALL
    else:
        if not session:
            session = get_session()
        stmt = select(UserCollection).where(
            UserCollection.user_id == user.id
            and UserCollection.collection_id == resource.collection_id
        )
        results = session.exec(stmt).first()
        if not results:
            return ResourcePermissionEnum.NONE
        if results.role == Role.MANAGER:
            return ResourcePermissionEnum.ALL
        if results.role == Role.MEMBER:
            return ResourcePermissionEnum.READ


def get_user_collections(
    user: User, session: Session, page: int, page_size: int
) -> CollectionsDto:
    #  TODO: Update this function to use the above
    try:
        _ = __get_user_system_permissions(user)
        where_clauses = (
            [UserCollection.user_id == user.id] if user and not user.is_admin else []
        )

        is_manager = func.coalesce(
            func.bool_or(UserCollection.role == Role.MANAGER).over(
                partition_by=Collection.id
            ),
            False,
        ).label("is_manager")

        statement = (
            select(Collection, is_manager)
            .join(UserCollection, isouter=True)
            .where(*where_clauses)
            .distinct()
            .order_by(Collection.id)
            .offset(page_size * (page - 1))
            .limit(page_size)
        )
        count_statement = select(func.count(Collection.id))
        query_results = session.exec(statement).all()

        # Build collections based on previous statements
        collections = [
            CollectionDto(
                id=collection.id,
                name=collection.name,
                description=collection.description,
                created_at=collection.created_at,
                is_manager=bool(is_manager),
            )
            for collection, is_manager in query_results
        ]

        total = session.exec(count_statement).one()

        return CollectionsDto(
            total=total,
            page=page,
            page_size=page_size,
            collections=collections,
            is_admin=user.is_admin if user else False,
        )
    except Exception as e:
        logger.error(f"Error retrieving available indexes: {str(e)}")
        raise NoPermissionException(
            error_code=500, message="Failed to retrieve available collections"
        )

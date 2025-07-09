from functools import lru_cache

from sqlmodel import Session, select

from api.enums import CollectionPermissionEnum, ResourcePermissionEnum
from api.environment import config
from api.models import (
    Collection,
    Resource,
    User,
    UserCollection,
)
from api.types import (
    Role,
)


@lru_cache
def get_session() -> Session:
    with Session(config.get_database()) as session:
        yield session


def __is_user_super_admin(user: User):
    return user.email in config.SUPER_ADMINS


def get_collection_permissions_for_user(
    user: User, collection: Collection, session: Session | None
) -> list[CollectionPermissionEnum]:
    if user.is_admin or __is_user_super_admin(user):
        return [
            CollectionPermissionEnum.VIEW,
            CollectionPermissionEnum.EDIT,
            CollectionPermissionEnum.DELETE,
            CollectionPermissionEnum.MANAGE_USERS,
            CollectionPermissionEnum.MANAGE_RESOURCES,
        ]
    else:
        if not session:
            session = get_session()
        stmt = select(UserCollection).where(
            UserCollection.user_id == user.id
            and UserCollection.collection_id == collection.id
        )
        results = session.exec(stmt).first()
        if not results:
            return []
        if results.role == Role.MANAGER:
            return [
                CollectionPermissionEnum.VIEW,
                CollectionPermissionEnum.EDIT,
                CollectionPermissionEnum.DELETE,
                CollectionPermissionEnum.MANAGE_USERS,
                CollectionPermissionEnum.MANAGE_RESOURCES,
            ]
        if results.role == Role.MEMBER:
            return [CollectionPermissionEnum.VIEW]
    return []


def get_resource_permissions_for_user(
    user: User, resource: Resource, session: Session | None
) -> list[ResourcePermissionEnum]:
    if user.is_admin or __is_user_super_admin(user):
        return [ResourcePermissionEnum.VIEW, ResourcePermissionEnum.DELETE]
    else:
        if not session:
            session = get_session()
        stmt = select(UserCollection).where(
            UserCollection.user_id == user.id
            and UserCollection.collection_id == resource.collection_id
        )
        results = session.exec(stmt).first()
        if not results:
            return []
        if results.role == Role.MANAGER:
            return [ResourcePermissionEnum.VIEW, ResourcePermissionEnum.DELETE]
        if results.role == Role.MEMBER:
            return [ResourcePermissionEnum.VIEW]

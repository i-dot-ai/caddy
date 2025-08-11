from functools import lru_cache
from uuid import UUID

from i_dot_ai_utilities.logging.structured_logger import StructuredLogger
from sqlmodel import Session, select

from api.enums import CollectionPermissionEnum, ResourcePermissionEnum
from api.environment import config
from api.exceptions import ItemNotFoundException, NoPermissionException
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


def is_user_admin_user(user: User):
    return user.email in config.admin_users or user.is_admin


def get_collection_permissions_for_user(
    user: User, collection: Collection, session: Session | None
) -> list[CollectionPermissionEnum]:
    if is_user_admin_user(user):
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
    if not session:
        session = get_session()
    stmt = select(UserCollection).where(
        UserCollection.user_id == user.id
        and UserCollection.collection_id == resource.collection_id
    )
    results = session.exec(stmt).first()
    if not results:
        return (
            []
            if not is_user_admin_user(user)
            else [ResourcePermissionEnum.VIEW, ResourcePermissionEnum.DELETE]
        )
    else:
        if results.role == Role.MANAGER or is_user_admin_user(user):
            return [
                ResourcePermissionEnum.VIEW,
                ResourcePermissionEnum.READ_CONTENTS,
                ResourcePermissionEnum.DELETE,
            ]
        if results.role == Role.MEMBER:
            return [ResourcePermissionEnum.VIEW, ResourcePermissionEnum.READ_CONTENTS]


def check_user_is_member_of_collection(
    user: User | None,
    collection_id: UUID,
    session: Session,
    struct_logger: StructuredLogger,
    is_manager_of_collection: bool = True,
):
    if user is None:
        struct_logger.info(
            "Anonymous access request for collection {collection_id} denied",
            collection_id=collection_id,
        )
        raise NoPermissionException(error_code=401, message="Unauthorised")

    if not session.get(Collection, collection_id):
        struct_logger.info(
            "Collection {collection_id} not found for route request for user {user_email}",
            collection_id=collection_id,
            user_email=str(user),
        )
        raise ItemNotFoundException(error_code=404, message="Collection Not Found")

    if user.is_admin:
        struct_logger.info(
            "user {user_email} has access to {collection_id} as they are an admin",
            user_email=str(user),
            collection_id=collection_id,
        )
        return

    user_collection = session.get(
        UserCollection, {"user_id": user.id, "collection_id": collection_id}
    )

    if not user_collection:
        struct_logger.info(
            "User {user_email} not allowed to see collection {collection_id}",
            user_email=str(user),
            collection_id=collection_id,
        )
        raise NoPermissionException(
            error_code=403, message="User is not a member of this collection"
        )

    if is_manager_of_collection and user_collection.role != Role.MANAGER:
        struct_logger.info(
            "User {user_email} must be a manager for this request to see collection {collection_id}",
            user_email=str(user),
            collection_id=collection_id,
        )
        raise NoPermissionException(
            error_code=403, message="User is not a manger of this collection"
        )

    struct_logger.info(
        "user {user_email} has access to {collection_id} as they are a {role}",
        user_email=str(user),
        collection_id=collection_id,
        role=user_collection.role,
    )

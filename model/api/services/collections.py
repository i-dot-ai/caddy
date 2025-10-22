from uuid import UUID

from i_dot_ai_utilities.logging.structured_logger import StructuredLogger
from markitdown import MarkItDown
from sqlalchemy import func
from sqlmodel import Session, select

from api.data_structures.enums import CollectionPermissionEnum
from api.data_structures.models import (
    Collection,
    User,
    UserCollection,
    UserCollectionWithEmail,
    UserRoleList,
)
from api.data_structures.types import (
    CollectionBase,
    CollectionDto,
    CollectionsDto,
    Role,
    UserRole,
)
from api.environments.environment import config
from api.utilities.exceptions import (
    DuplicateItemException,
    ItemNotFoundException,
    NoPermissionException,
)
from api.utilities.permissions import (
    check_user_is_member_of_collection,
    get_collection_permissions_for_user,
    is_user_admin_user,
)

metric_writer = config.get_metrics_writer()
md = MarkItDown()


def create_new_collection(
    new_collection: CollectionBase,
    session: Session,
    user: User,
    logger: StructuredLogger,
) -> Collection:
    collection = Collection(**new_collection.model_dump())
    stmt = select(Collection).where(Collection.name == collection.name)
    results = session.exec(stmt).all()
    if results:
        logger.info(
            "A collection with name {collection_name} already exists",
            collection_name=collection.name,
        )
        raise DuplicateItemException(
            error_code=422, message="A collection with this name already exists"
        )
    session.add(collection)
    session.commit()
    session.refresh(collection)

    user_collection = UserCollection(
        user_id=user.id,
        collection_id=collection.id,
        role=Role.MANAGER,
    )
    session.add(user_collection)
    session.commit()
    session.refresh(collection)

    logger.info(
        "Collection {collection_name} created by user {user_email}",
        collection_name=collection.name,
        user_email=str(user),
    )

    return collection


def get_user_collections(
    user: User,
    session: Session,
    logger: StructuredLogger,
    page: int = 1,
    page_size: int = 10,
) -> CollectionsDto:
    try:
        user_is_admin = is_user_admin_user(user) or user.is_admin
        where_clauses = (
            [UserCollection.user_id == user.id] if user and not user.is_admin else []
        )

        statement = (
            select(Collection)
            .join(UserCollection, isouter=True)
            .where(*where_clauses)
            .distinct()
            .order_by(Collection.name)
            .offset(page_size * (page - 1))
            .limit(page_size)
        )
        count_statement = (
            select(func.count(Collection.id))
            .join(UserCollection, isouter=True)
            .where(*where_clauses)
            .distinct()
        )
        query_results = session.exec(statement).all()
        logger.info("Found {count} collections from query", count=len(query_results))

        # Build collections based on previous statements

        collections = []
        for collection in query_results:
            permissions = get_collection_permissions_for_user(user, collection, session)
            if CollectionPermissionEnum.VIEW not in permissions:
                logger.error(
                    "User {user_email} does not have permission to view {collection}",
                    user_email=str(user),
                    collection=collection.id,
                )
                raise NoPermissionException(
                    error_code=401, message="Failed to retrieve available collections"
                )
            collections.append(
                CollectionDto(
                    id=collection.id,
                    name=collection.name,
                    description=collection.description,
                    created_at=collection.created_at,
                    permissions=permissions,
                    custom_prompt=collection.custom_prompt,
                )
            )

        total = session.exec(count_statement).one()

        return CollectionsDto(
            total=total,
            page=page,
            page_size=page_size,
            collections=collections,
            is_admin=user_is_admin,
        )
    except Exception:
        raise


def update_collection_by_id(
    collection_id: UUID,
    collection_details: CollectionBase,
    session: Session,
    user: User,
    logger: StructuredLogger,
) -> CollectionDto:
    if collection := session.get(Collection, collection_id):
        permissions = get_collection_permissions_for_user(user, collection, session)
        if (
            CollectionPermissionEnum.EDIT not in permissions
            or CollectionPermissionEnum.VIEW not in permissions
        ):
            raise NoPermissionException(
                error_code=401, message="Permission to edit collection not found"
            )
        collection.name = collection_details.name
        collection.description = collection_details.description
        collection.custom_prompt = collection_details.custom_prompt
        session.add(collection)
        session.commit()
        session.refresh(collection)

        logger.info(
            "Collection {collection_name} updated by user {user_email}",
            collection_name=collection.name,
            user_email=str(user),
        )
        return CollectionDto(
            id=collection.id,
            name=collection.name,
            description=collection.description,
            created_at=collection.created_at,
            permissions=permissions,
            custom_prompt=collection.custom_prompt,
        )
    else:
        logger.info("Collection {collection_id} not found", collection_id=collection_id)
        raise ItemNotFoundException(message="Collection not found", error_code=403)


def delete_collection_by_id(
    user: User, collection_id: UUID, session: Session, logger: StructuredLogger
) -> UUID:
    check_user_is_member_of_collection(
        user, collection_id, session, struct_logger=logger
    )
    if collection := session.get(Collection, collection_id):
        permissions = get_collection_permissions_for_user(user, collection, session)
        if CollectionPermissionEnum.DELETE not in permissions:
            raise NoPermissionException(
                "Permission to delete collection not found", 401
            )
        s3_client = config.get_file_store_client()
        objects = s3_client.list_objects(prefix=f"{collection_id}")
        if objects:
            object_keys = [obj["Key"] for obj in objects]
            for object_key in object_keys:
                s3_client.delete_object(key=object_key)

        session.delete(collection)
        session.commit()
        logger.info(
            "Collection {collection_id}:{collection_name} deleted",
            collection_id=collection_id,
            collection_name=collection.name,
        )
        return collection_id
    else:
        raise ItemNotFoundException(error_code=404, message="Collection not found")


def get_collection_user_roles_by_id(
    user: User,
    session: Session,
    collection_id: UUID,
    logger: StructuredLogger,
    page: int = 1,
    page_size: int = 10,
) -> UserRoleList:
    check_user_is_member_of_collection(
        user, collection_id, session, struct_logger=logger
    )

    if session.get(Collection, collection_id):
        permissions = get_collection_permissions_for_user(user, collection_id, session)
        if (
            CollectionPermissionEnum.VIEW not in permissions
            or CollectionPermissionEnum.MANAGE_USERS not in permissions
        ):
            raise NoPermissionException(
                error_code=401, message="No permission to view this collections users"
            )

        statement = (
            select(UserCollection, User.email.label("user_email"))
            .where(UserCollection.collection_id == collection_id)
            .join(User, UserCollection.user_id == User.id)
            .order_by(User.email)
            .offset(page_size * (page - 1))
            .limit(page_size)
        )
        user_roles = session.exec(statement).all()

        user_roles_with_emails: list[UserCollectionWithEmail] = [
            UserCollectionWithEmail(user_email=email, **ur.model_dump())
            for ur, email in user_roles
        ]

        count_statement = func.count(UserCollection.user_id)
        total = session.exec(count_statement).scalar()
        logger.info(
            "Retrieved user roles for collection {collection_id} for user {user_email}. {total} user(s) retrieved",
            collection_id=collection_id,
            user_email=str(user),
            total=total,
        )
        return UserRoleList(
            page=page,
            page_size=page_size,
            total=total,
            user_roles=user_roles_with_emails,
        )
    else:
        raise ItemNotFoundException(error_code=404, message="Collection not found")


def create_user_role_on_collection(
    user: User,
    session: Session,
    user_role: UserRole,
    collection_id: UUID,
    logger: StructuredLogger,
) -> UserCollection:
    if collection := session.get(Collection, collection_id):
        check_user_is_member_of_collection(
            user, collection_id, session, struct_logger=logger
        )

        permissions = get_collection_permissions_for_user(user, collection, session)
        if CollectionPermissionEnum.MANAGE_USERS not in permissions:
            raise NoPermissionException(
                error_code=401, message="No permission to manage users"
            )

        user_to_add = User.get_by_email(session, user_role.email.lower())

        if not user_to_add:
            user_to_add = User(email=user_role.email.lower())
            session.add(user_to_add)
            session.commit()
            session.refresh(user_to_add)

        if user_collection := session.get(
            UserCollection, {"collection_id": collection_id, "user_id": user_to_add.id}
        ):
            user_collection.role = user_role.role
        else:
            user_collection = UserCollection(
                collection_id=collection_id,
                user_id=user_to_add.id,
                role=user_role.role,
            )

        session.add(user_collection)
        session.commit()
        session.refresh(user_collection)
        logger.info(
            "Role {role} for user {user_email} created on collection {collection_id}",
            role=user_role.role,
            user_email=str(user_to_add),
            collection_id=collection_id,
        )
        return user_collection
    else:
        raise ItemNotFoundException(error_code=404, message="Collection not found")


def delete_user_role_from_collection(
    user: User,
    session: Session,
    collection_id: UUID,
    user_id: UUID,
    logger: StructuredLogger,
) -> bool:
    if collection := session.get(Collection, collection_id):
        if not session.get(User, user_id):
            raise ItemNotFoundException(
                error_code=404, message="User to remove not found"
            )

        if user_role := session.get(
            UserCollection, {"user_id": user_id, "collection_id": collection_id}
        ):
            check_user_is_member_of_collection(
                user, collection_id, session, struct_logger=logger
            )

            permissions = get_collection_permissions_for_user(user, collection, session)

            if CollectionPermissionEnum.MANAGE_USERS not in permissions:
                raise NoPermissionException(
                    error_code=401,
                    message="No permission to manage users for this collection",
                )

            session.delete(user_role)
            session.commit()
            logger.info(
                "User role for collection {collection_id} deleted for user {user_email}",
                collection_id=collection_id,
                user_email=str(user),
            )
            return True
        else:
            raise ItemNotFoundException(
                error_code=404, message="User is not added to the given collection"
            )
    else:
        raise ItemNotFoundException(error_code=404, message="Collection not found")

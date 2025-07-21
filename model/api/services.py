from uuid import UUID

from i_dot_ai_utilities.logging.structured_logger import StructuredLogger
from sqlalchemy import func
from sqlmodel import Session, select

from api.enums import CollectionPermissionEnum
from api.exceptions import (
    DuplicateItemException,
    ItemNotFoundException,
    NoPermissionException,
)
from api.models import (
    Collection,
    CollectionResources,
    Resource,
    User,
    UserCollection,
)
from api.permissions import (
    check_user_is_member_of_collection,
    get_collection_permissions_for_user,
    get_resource_permissions_for_user,
    is_user_admin_user,
)
from api.types import (
    CollectionBase,
    CollectionDto,
    CollectionsDto,
    Role,
)


def get_resources_by_collection_id(
    user: User,
    session: Session,
    collection_id: UUID,
    logger: StructuredLogger,
    page_size: int = 10,
    page: int = 1,
) -> CollectionResources:
    if collection := session.get(Collection, collection_id):
        check_user_is_member_of_collection(
            user, collection.id, session, is_manager=False, struct_logger=logger
        )
        permissions = get_collection_permissions_for_user(user, collection, session)
        if permissions is None or CollectionPermissionEnum.VIEW not in permissions:
            raise NoPermissionException(
                "No permission to view resources on this collection", 401
            )
        resources_statement = (
            select(Resource)
            .where(Resource.collection_id == collection.id)
            .order_by(Resource.filename)
            .offset(page_size * (page - 1))
            .limit(page_size)
        )
        resources = session.exec(resources_statement).all()

        count_statement = select(func.count(Resource.id)).where(
            Resource.collection_id == collection.id
        )
        total = session.scalar(count_statement)

        logger.info(
            "Retrieved collection {collection_id} resources ({resource_count}) for user {user_id}",
            collection_id=collection.id,
            resource_count=total,
            user_id=user.id,
        )

        for resource in resources:
            resource.permissions = get_resource_permissions_for_user(
                user, resource, session
            )

        return CollectionResources(
            collection_id=collection.id,
            page=page,
            total=total,
            page_size=page_size,
            resources=resources,
        )
    else:
        raise ItemNotFoundException("Collection not found", 403)


def create_new_collection(
    new_collection: CollectionBase,
    session: Session,
    user: User,
    logger: StructuredLogger,
) -> Collection:
    if not user.is_admin:
        logger.info(
            "User {user} tried to create a collection {collection_name} without being an admin",
            user=user.email,
            collection_name=new_collection.collection_name,
        )
        raise NoPermissionException(error_code=403, message="User needs to be an admin")
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
        "Collection {collection_name} created by user {user}",
        collection_name=collection.name,
        user=user.email,
    )

    return collection


def get_user_collections(
    user: User,
    session: Session,
    logger: StructuredLogger,
    page: int = 1,
    page_size: int = 10,
) -> CollectionsDto:
    user_is_admin = is_user_admin_user(user) or user.is_admin
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

    collections = []
    for collection, is_manager in query_results:
        permissions = get_collection_permissions_for_user(user, collection, session)
        if CollectionPermissionEnum.VIEW not in permissions:
            logger.error(msg="No permission to view collection")
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
                is_manager=is_manager,
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

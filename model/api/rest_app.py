from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from i_dot_ai_utilities.logging.structured_logger import StructuredLogger
from langchain_core.documents import Document
from markitdown import MarkItDown, MarkItDownException
from sqlalchemy import func
from sqlmodel import Session, select

from api.auth import get_current_user
from api.depends import get_logger
from api.environment import config, get_session
from api.exceptions import (
    DuplicateItemException,
    ItemNotFoundException,
    NoPermissionException,
)
from api.models import (
    Collection,
    CollectionResources,
    Resource,
    TextChunk,
    User,
    UserCollection,
    UserCollectionWithEmail,
    UserRoleList,
)
from api.services import (
    create_new_collection,
    create_resource_from_file,
    create_resource_from_urls,
    delete_collection_by_id,
    get_resources_by_collection_id,
    get_user_collections,
    update_collection_by_id,
)
from api.types import (
    Chunks,
    CollectionBase,
    CollectionDto,
    CollectionsDto,
    UserRole,
)

router = APIRouter()  # Create an APIRouter instance
md = MarkItDown()
metric_writer = config.get_metrics_writer()


@router.get(
    "/collections/{collection_id}/resources", status_code=200, tags=["collections"]
)
def get_collection_resources(
    collection_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    logger: StructuredLogger = Depends(get_logger(__name__)),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
) -> CollectionResources:
    """returns a list of resources belonging to this collection"""
    try:
        return get_resources_by_collection_id(
            user, session, collection_id, logger, page_size, page
        )
    except NoPermissionException as e:
        logger.exception(
            "Unable to return resources for collection {collection_id}",
            collection_id=collection_id,
        )
        raise HTTPException(
            status_code=e.error_code,
            detail=e.message,
        )
    except ItemNotFoundException as e:
        logger.exception(
            "Collection {collection_id} not found", collection_id=collection_id
        )
        raise HTTPException(
            status_code=e.error_code,
            detail=e.message,
        )


@router.post("/collections", status_code=201, tags=["collections"])
def create_collection(
    new_collection: CollectionBase,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    logger: StructuredLogger = Depends(get_logger(__name__)),
) -> Collection:
    """create a collection"""
    try:
        result = create_new_collection(new_collection, session, user, logger)
    except NoPermissionException as e:
        logger.exception(
            "An issue occurred creating collection {collection_name} by user {user_email}",
            collection_name=new_collection.collection_name,
            user_email=user.email,
        )
        raise HTTPException(status_code=e.error_code, detail=str(e))
    except DuplicateItemException as e:
        logger.exception(
            "A collection with this name already exists. {collection_name}",
            collection_name=new_collection.collection_name,
        )
        raise HTTPException(status_code=e.error_code, detail=str(e))
    else:
        return result


@router.put("/collections/{collection_id}", status_code=200, tags=["collections"])
def update_collection(
    collection_id: UUID,
    collection_details: CollectionBase,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    logger: StructuredLogger = Depends(get_logger(__name__)),
) -> CollectionDto:
    """update a collection"""
    try:
        result = update_collection_by_id(
            collection_id, collection_details, session, user, logger
        )
    except NoPermissionException as e:
        logger.exception(
            "User {user_email} doesn't have permission to edit collection {collection_name}",
            user_email=user.email,
            collection_name=collection_details.collection_name,
        )
        raise HTTPException(status_code=e.error_code, detail=str(e))
    except ItemNotFoundException as e:
        logger.exception(
            "Collection {collection_id} not found", collection_id=collection_id
        )
        raise HTTPException(status_code=e.error_code, detail=str(e))
    else:
        return result


@router.delete("/collections/{collection_id}", status_code=200, tags=["collections"])
def delete_collection(
    collection_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    logger: StructuredLogger = Depends(get_logger(__name__)),
) -> UUID:
    """delete a collection"""
    try:
        result = delete_collection_by_id(user, collection_id, session, logger)
    except NoPermissionException as e:
        logger.exception(
            "User {user_email} doesn't have permission to delete collection {collection_id}",
            user_email=user.email,
            collection_id=collection_id,
        )
        raise HTTPException(status_code=e.error_code, detail=str(e))
    except ItemNotFoundException as e:
        logger.exception(
            "Collection {collection_id} not found", collection_id=collection_id
        )
        raise HTTPException(status_code=e.error_code, detail=str(e))
    else:
        return result


@router.post(
    "/collections/{collection_id}/resources", status_code=201, tags=["resources"]
)
def create_resource(
    collection_id: UUID,
    file: Annotated[UploadFile, File(...)],
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    logger: StructuredLogger = Depends(get_logger(__name__)),
) -> Resource:
    """
    Endpoint to upload a file to a specified collection.

    Args:
        logger: The logger to use
        session: DB session
        user: The logged-in user from auth JWT or None
        collection_id (str): The collection to upload the file to.
        file (Annotated[UploadFile, File()]): The file being uploaded.

    Returns:
        Resource
    """
    try:
        result = create_resource_from_file(user, collection_id, session, logger, file)
    except NoPermissionException as e:
        logger.exception(
            "Permission to create resources on collection {collection_id} failed",
            collection_id=collection_id,
        )
        raise HTTPException(status_code=e.error_code, detail=str(e))
    except ItemNotFoundException as e:
        logger.exception(
            "Collection {collection_id} not found", collection_id=collection_id
        )
        raise HTTPException(status_code=e.error_code, detail=str(e))
    except MarkItDownException:
        logger.exception("An error in markitdown occurred")
        raise HTTPException(detail="An error in markitdown occurred", status_code=500)
    else:
        return result


@router.post(
    "/collections/{collection_id}/resources/urls", status_code=201, tags=["resources"]
)
async def create_resources_from_url_list(
    collection_id: UUID,
    urls: list[str],
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    logger: StructuredLogger = Depends(get_logger(__name__)),
) -> list[Resource]:
    """
    Endpoint to upload a file to a specified collection.

    Args:
        logger: The logger to use
        session: DB session
        user: The logged-in user from auth JWT or None
        collection_id (str): The collection to upload the file to.
        urls (list[str]): The urls being uploaded.

    Returns:
        Resources
    """
    try:
        result = await create_resource_from_urls(
            user, session, collection_id, logger, urls
        )
    except NoPermissionException as e:
        logger.exception(
            "Permission to create resources on collection {collection_id} failed",
            collection_id=collection_id,
        )
        raise HTTPException(status_code=e.error_code, detail=str(e))
    except ItemNotFoundException as e:
        logger.exception(
            "Collection {collection_id} not found", collection_id=collection_id
        )
        raise HTTPException(status_code=e.error_code, detail=str(e))
    else:
        return result


@router.get(
    "/collections/{collection_id}/resources/{resource_id}/documents",
    status_code=200,
    tags=["resources"],
)
def get_resource_documents(
    collection_id: UUID,
    resource_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    logger: StructuredLogger = Depends(get_logger(__name__)),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
) -> Chunks:
    """get a documents belonging to a resource"""

    __check_user_is_member_of_collection(
        user, collection_id, session, is_manager=False, struct_logger=logger
    )

    if not session.get(Resource, resource_id):
        logger.info("Resource with id {resource_id} not found", resource_id=resource_id)
        raise HTTPException(status_code=404)

    statement = (
        select(TextChunk)
        .where(TextChunk.resource_id == resource_id)
        .order_by(TextChunk.order)
        .offset(page_size * (page - 1))
        .limit(page_size)
    )

    text_chunks = session.exec(statement).all()

    def to_document(tc: TextChunk):
        return Document(
            page_content=tc.text,
            id=str(tc.id),
            metadata={
                "resource_id": tc.resource_id,
                "filename": tc.resource.filename,
                "content_type": tc.resource.content_type,
                "chunk_order": tc.order,
                "created_at": tc.created_at,
            },
        )

    documents = [to_document(item) for item in text_chunks]

    count_statement = select(func.count(TextChunk.id)).where(
        TextChunk.resource_id == resource_id
    )
    total = session.exec(count_statement).one()

    logger.info(
        "{total} document(s) for resource {resource_id} retrieved by user {user}",
        total=total,
        resource_id=resource_id,
        user=user,
    )

    return Chunks(
        collection_id=collection_id,
        resource_id=resource_id,
        page=page,
        total=total,
        page_size=page_size,
        documents=documents,
    )


@router.delete(
    "/collections/{collection_id}/resources/{resource_id}",
    status_code=200,
    tags=["resources"],
)
def delete_resource(
    collection_id: UUID,
    resource_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    logger: StructuredLogger = Depends(get_logger(__name__)),
) -> UUID:
    """delete a resource"""
    __check_user_is_member_of_collection(
        user, collection_id, session, struct_logger=logger
    )

    config.s3_client.delete_object(
        Bucket=config.data_s3_bucket,
        Key=f"{config.s3_prefix}/{collection_id}/{resource_id}",
    )

    if resource := session.get(Resource, resource_id):
        session.delete(resource)
        session.commit()
        logger.info("Resource {resource_id} deleted", resource_id=resource_id)
        return resource_id
    else:
        logger.info("Resource {resource_id} not found", resource_id=resource_id)
        raise HTTPException(status_code=404)


@router.get(
    "/collections/{collection_id}/resources/{resource_id}",
    status_code=200,
    tags=["resources"],
)
def get_resource(
    collection_id: UUID,
    resource_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    logger: StructuredLogger = Depends(get_logger(__name__)),
) -> Resource:
    """get a resource"""
    __check_user_is_member_of_collection(
        user, collection_id, session, is_manager=False, struct_logger=logger
    )

    if resource := session.get(Resource, resource_id):
        logger.info("Resource {resource_id} found", resource_id=resource_id)
        return resource
    logger.info("Resource {resource_id} not found", resource_id=resource_id)
    raise HTTPException(status_code=404)


@router.get("/collections", status_code=200, tags=["collections"])
def get_collections(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    logger: StructuredLogger = Depends(get_logger(__name__)),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
) -> CollectionsDto:
    """Get a list of all available collections.
    Args:
        logger: The logger to use
        session: DB session
        user: Logged-in user or none from JWT
        page: Page number
        page_size: Number of records for each page
    Returns:
        CollectionList: List of available collections available to currently logged-in user
    Raises:
        HTTPException: 500 status code if collection retrieval fails
    """
    logger.info("Getting collections for user: {user}".format(user=user.email))
    try:
        return get_user_collections(user, session, logger, page, page_size)
    except NoPermissionException as e:
        logger.exception(
            "Error retrieving available collections for user {user_email}",
            user=user.email,
        )
        raise HTTPException(status_code=e.error_code, detail=e.message)
    except Exception:
        logger.exception(
            "Error retrieving available collections for user {user}", user=user.email
        )
        raise HTTPException(
            status_code=500, detail="Failed to retrieve available collections"
        )


@router.get("/collections/{collection_id}/users", status_code=200, tags=["user-roles"])
def get_collections_user_roles(
    collection_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    logger: StructuredLogger = Depends(get_logger(__name__)),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
) -> UserRoleList:
    __check_user_is_member_of_collection(
        user, collection_id, session, struct_logger=logger
    )

    statement = (
        select(UserCollection, User.email.label("user_email"))
        .where(UserCollection.collection_id == collection_id)
        .join(User, UserCollection.user_id == User.id)
        .order_by(UserCollection.created_at)
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
        "Retrieved user roles for collection {collection_id} for user {user}. {total} user(s) retrieved",
        collection_id=collection_id,
        user=user.email,
        total=total,
    )
    return UserRoleList(
        page=page, page_size=page_size, total=total, user_roles=user_roles_with_emails
    )


@router.post("/collections/{collection_id}/users", status_code=201, tags=["user-roles"])
def create_collections_user_role(
    collection_id: UUID,
    user_role: UserRole,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    logger: StructuredLogger = Depends(get_logger(__name__)),
) -> UserCollection:
    __check_user_is_member_of_collection(
        user, collection_id, session, struct_logger=logger
    )

    user = User.get_by_email(session, user_role.email)

    if not user:
        user = User(email=user_role.email)
        session.add(user)
        session.commit()
        session.refresh(user)

    if not session.get(Collection, collection_id):
        logger.info(
            "Failed to find collection {collection_id}", collection_id=collection_id
        )
        raise HTTPException(status_code=404, detail="Collection not found")

    if user_collection := session.get(
        UserCollection, {"collection_id": collection_id, "user_id": user.id}
    ):
        user_collection.role = user_role.role
    else:
        user_collection = UserCollection(
            collection_id=collection_id,
            user_id=user.id,
            role=user_role.role,
        )

    session.add(user_collection)
    session.commit()
    session.refresh(user_collection)
    logger.info(
        "Role {role} for user {user} created on collection {collection_id}",
        role=user_role.role,
        user=user.email,
        collection_id=collection_id,
    )
    return user_collection


@router.delete(
    "/collections/{collection_id}/users/{user_id}",
    status_code=200,
    tags=["user-roles"],
)
def delete_collections_user_role(
    collection_id: UUID,
    user_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    logger: StructuredLogger = Depends(get_logger(__name__)),
) -> bool:
    __check_user_is_member_of_collection(
        user, collection_id, session, struct_logger=logger
    )

    if user_role := session.get(
        UserCollection, {"collection_id": collection_id, "user_id": user_id}
    ):
        session.delete(user_role)
        session.commit()
        logger.info(
            "User role for collection {collection_id} deleted for user {user}",
            collection_id=collection_id,
            user=user.email,
        )
        return True
    logger.info(
        "Failed to delete user role for user {user} from collection {collection_id}",
        user=user.email,
        collection_id=collection_id,
    )
    raise HTTPException(status_code=404)

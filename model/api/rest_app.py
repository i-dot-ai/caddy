from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from i_dot_ai_utilities.logging.structured_logger import StructuredLogger
from markitdown import MarkItDown, MarkItDownException
from sqlmodel import Session

from api.auth import get_current_user
from api.depends import get_logger
from api.environment import config, get_session
from api.exceptions import (
    DuplicateItemException,
    InvalidUrlFormatException,
    ItemNotFoundException,
    NoPermissionException,
)
from api.models import (
    Collection,
    User,
    UserCollection,
    UserRoleList,
)
from api.services import (
    create_new_collection,
    create_resource_from_file,
    create_resource_from_urls,
    create_user_role_on_collection,
    delete_collection_by_id,
    delete_resource_by_id,
    delete_user_role_from_collection,
    get_collection_user_roles_by_id,
    get_documents_for_resource_by_id,
    get_resource_by_id,
    get_resource_download_url,
    get_resources_by_collection_id,
    get_user_collections,
    update_collection_by_id,
)
from api.types import (
    Chunks,
    CollectionBase,
    CollectionDto,
    CollectionResources,
    CollectionsDto,
    ResourceDto,
    UserRole,
)

router = APIRouter()  # Create an APIRouter instance
md = MarkItDown()
metric_writer = config.get_metrics_writer()


def __set_logger_context(logger: StructuredLogger, user: User):
    logger.set_context_field("user_email", str(user))
    logger.set_context_field("user_id", str(user.id))


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
        __set_logger_context(logger, user)
        result = get_resources_by_collection_id(
            user, session, collection_id, logger, page_size, page
        )
    except (NoPermissionException, ItemNotFoundException) as e:
        logger.exception(
            "An exception occurred getting collection resources {message}",
            message=str(e),
        )
        raise HTTPException(
            status_code=e.error_code,
            detail=e.message,
        )
    else:
        resource_ids = [str(resource.id) for resource in result.resources]
        logger.info(
            "Resources {resource_ids} retrieved for collection {collection_id}",
            resource_ids=",".join(resource_ids),
            collection_id=collection_id,
        )
        return result


@router.post("/collections", status_code=201, tags=["collections"])
def create_collection(
    new_collection: CollectionBase,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    logger: StructuredLogger = Depends(get_logger(__name__)),
) -> Collection:
    """create a collection"""
    try:
        __set_logger_context(logger, user)
        result = create_new_collection(new_collection, session, user, logger)
    except (NoPermissionException, DuplicateItemException) as e:
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
        __set_logger_context(logger, user)
        result = update_collection_by_id(
            collection_id, collection_details, session, user, logger
        )
    except (NoPermissionException, ItemNotFoundException) as e:
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
        __set_logger_context(logger, user)
        result = delete_collection_by_id(user, collection_id, session, logger)
    except (NoPermissionException, ItemNotFoundException) as e:
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
) -> ResourceDto:
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
        __set_logger_context(logger, user)
        result = create_resource_from_file(user, collection_id, session, logger, file)
    except (NoPermissionException, ItemNotFoundException) as e:
        raise HTTPException(status_code=e.error_code, detail=str(e))
    except MarkItDownException:
        raise HTTPException(
            detail="An issue occurred processing this file", status_code=422
        )
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
) -> list[ResourceDto]:
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
        __set_logger_context(logger, user)
        result = await create_resource_from_urls(
            user, session, collection_id, logger, urls
        )
    except (
        NoPermissionException,
        ItemNotFoundException,
        InvalidUrlFormatException,
    ) as e:
        raise HTTPException(status_code=e.error_code, detail=str(e))
    else:
        return result


@router.get(
    "/collections/{collection_id}/resources/{resource_id}/download",
    status_code=302,
    tags=["resources"],
)
def get_download_url(
    collection_id: UUID,
    resource_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    logger: StructuredLogger = Depends(get_logger(__name__)),
) -> str:
    """
    Endpoint to download a file, if authorised.

    Args:
        logger: The logger to use
        session: DB session
        user: The logged-in user from auth JWT or None
        collection_id (UUID): The collection the file belongs to.
        resource_id (UUID): The resource to download.

    Returns:
        A redirect to the download url
    """
    try:
        __set_logger_context(logger, user)
        result = get_resource_download_url(
            collection_id, resource_id, session, logger, user
        )
    except (
        NoPermissionException,
        ItemNotFoundException,
    ) as e:
        logger.exception(
            "Failed to get download url for resource {resource_id} for user {user_email}",
            resource_id=resource_id,
            user_email=str(user),
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
    try:
        __set_logger_context(logger, user)
        result = get_documents_for_resource_by_id(
            user, collection_id, session, logger, resource_id, page, page_size
        )
    except (NoPermissionException, ItemNotFoundException) as e:
        raise HTTPException(status_code=e.error_code, detail=str(e))
    else:
        return result


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
    try:
        __set_logger_context(logger, user)
        result = delete_resource_by_id(
            user, session, collection_id, resource_id, logger
        )
    except (NoPermissionException, ItemNotFoundException) as e:
        raise HTTPException(status_code=e.error_code, detail=str(e))
    else:
        return result


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
) -> ResourceDto:
    """get a resource"""
    try:
        __set_logger_context(logger, user)
        result = get_resource_by_id(user, session, collection_id, resource_id, logger)
    except (NoPermissionException, ItemNotFoundException) as e:
        raise HTTPException(status_code=e.error_code, detail=str(e))
    else:
        return result


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
    """
    try:
        __set_logger_context(logger, user)
        logger.info("Getting collections for user {user_email}", user_email=str(user))
        result = get_user_collections(user, session, logger, page, page_size)
        logger.info("Successfully got collections: {count} total", count=result.total)
    except NoPermissionException as e:
        logger.exception(
            "Exception occurred getting collections. {message}", message=str(e)
        )
        raise HTTPException(status_code=e.error_code, detail=e.message)
    else:
        collection_ids = (
            [str(collection.id) for collection in result.collections]
            if result.collections
            else []
        )
        logger.info("Returning collections {ids}", ids=", ".join(collection_ids))
        return result


@router.get("/collections/{collection_id}/users", status_code=200, tags=["user-roles"])
def get_collections_user_roles(
    collection_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    logger: StructuredLogger = Depends(get_logger(__name__)),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
) -> UserRoleList:
    try:
        __set_logger_context(logger, user)
        result = get_collection_user_roles_by_id(
            user, session, collection_id, logger, page, page_size
        )
    except (NoPermissionException, ItemNotFoundException) as e:
        raise HTTPException(status_code=e.error_code, detail=str(e))
    else:
        return result


@router.post("/collections/{collection_id}/users", status_code=201, tags=["user-roles"])
def create_collections_user_role(
    collection_id: UUID,
    user_role: UserRole,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    logger: StructuredLogger = Depends(get_logger(__name__)),
) -> UserCollection:
    try:
        __set_logger_context(logger, user)
        result = create_user_role_on_collection(
            user, session, user_role, collection_id, logger
        )
    except (NoPermissionException, ItemNotFoundException) as e:
        raise HTTPException(status_code=e.error_code, detail=str(e))
    else:
        return result


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
    try:
        __set_logger_context(logger, user)
        result = delete_user_role_from_collection(
            user, session, collection_id, user_id, logger
        )
    except (NoPermissionException, ItemNotFoundException) as e:
        raise HTTPException(status_code=e.error_code, detail=str(e))
    else:
        return result

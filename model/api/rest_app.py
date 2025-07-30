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
    download_resource_for_user,
    get_collection_user_roles_by_id,
    get_documents_for_resource_by_id,
    get_resource_by_id,
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
        result = get_resources_by_collection_id(
            user, session, collection_id, logger, page_size, page
        )
    except (NoPermissionException, ItemNotFoundException) as e:
        raise HTTPException(
            status_code=e.error_code,
            detail=e.message,
        )
    else:
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
    logger.info("Getting collections for user: {user}".format(user=user.email))
    try:
        result = get_user_collections(user, session, logger, page, page_size)
    except NoPermissionException as e:
        raise HTTPException(status_code=e.error_code, detail=e.message)
    else:
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
        result = delete_user_role_from_collection(
            user, session, collection_id, user_id, logger
        )
    except (NoPermissionException, ItemNotFoundException) as e:
        raise HTTPException(status_code=e.error_code, detail=str(e))
    else:
        return result


@router.get(
    "/collections/{collection_id}/resources/{resource_id}/download",
    status_code=200,
    tags=["resources"],
)
def download_resource(
    collection_id: UUID,
    resource_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    logger: StructuredLogger = Depends(get_logger(__name__)),
):
    try:
        result = download_resource_for_user(
            user, session, collection_id, resource_id, logger
        )
    except (NoPermissionException, ItemNotFoundException) as e:
        raise HTTPException(status_code=e.error_code, detail=str(e))
    else:
        return result

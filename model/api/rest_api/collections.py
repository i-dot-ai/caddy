from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from i_dot_ai_utilities.logging.structured_logger import StructuredLogger
from markitdown import MarkItDown
from sqlmodel import Session

from api.auth import get_current_user
from api.data_structures.models import (
    Collection,
    User,
    UserCollection,
    UserRoleList,
)
from api.data_structures.types import (
    CollectionBase,
    CollectionDto,
    CollectionsDto,
    UserRole,
)
from api.environments.environment import config, get_session
from api.services.collections import (
    create_new_collection,
    create_user_role_on_collection,
    delete_collection_by_id,
    delete_user_role_from_collection,
    get_collection_user_roles_by_id,
    get_user_collections,
    update_collection_by_id,
)
from api.utilities.depends import get_logger
from api.utilities.exceptions import (
    DuplicateItemException,
    ItemNotFoundException,
    NoPermissionException,
)

router = APIRouter()  # Create an APIRouter instance
md = MarkItDown()
metric_writer = config.get_metrics_writer()


def __set_logger_context(logger: StructuredLogger, user: User):
    logger.set_context_field("user_email", str(user))
    logger.set_context_field("user_id", str(user.id))


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

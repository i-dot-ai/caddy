from logging import getLogger

from sqlalchemy import func
from sqlmodel import Session, select

from api.enums import CollectionPermissionEnum
from api.exceptions import NoPermissionException
from api.models import (
    Collection,
    User,
    UserCollection,
)
from api.permissions import get_collection_permissions_for_user, is_user_super_admin
from api.types import (
    CollectionDto,
    CollectionsDto,
    Role,
)

logger = getLogger(__name__)


def get_user_collections(
    user: User, session: Session, page: int, page_size: int
) -> CollectionsDto:
    user_is_admin = is_user_super_admin(user) or user.is_admin
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
                name=collection.id if user_is_admin else collection.name,
                description=collection.id if user_is_admin else collection.description,
                created_at=collection.created_at,
                is_manager=bool(is_manager),
                # permission=,
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

from logging import getLogger

from sqlalchemy import func
from sqlmodel import Session, select

from api.models import (
    Collection,
    User,
    UserCollection,
)
from api.permissions import get_collection_permissions_for_user
from api.types import (
    CollectionDto,
    CollectionsDto,
    Role,
)

logger = getLogger(__name__)


class NoPermissionException(Exception):
    """Exception raised for custom error in the application."""

    def __init__(self, message, error_code):
        super().__init__(message)
        self.error_code = error_code
        self.message = message

    def __str__(self):
        return f"{self.message} (Error Code: {self.error_code})"


def get_user_collections(
    user: User, session: Session, page: int, page_size: int
) -> CollectionsDto:
    #  TODO: Update this function to use the above
    try:
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
                permission=get_collection_permissions_for_user(
                    user, collection, session
                ),
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

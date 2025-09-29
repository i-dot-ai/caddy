from typing import Annotated

from fastapi import Depends, Header, HTTPException
from i_dot_ai_utilities.logging.structured_logger import StructuredLogger
from sqlmodel import Session, select

from api.auth.token_auth import get_authorised_user
from api.depends import get_logger
from api.environment import get_session
from api.models import User


def get_current_user(
    session: Annotated[Session, Depends(get_session)],
    authorization: Annotated[str, Header()] = None,
    logger: StructuredLogger = Depends(get_logger(__name__)),
) -> User | None:  # noqa: RUF013, PLR0912, C901
    """
    Called on every endpoint to decode JWT in every request header under the name "Authorization"
    Gets or creates the user based on the email in the JWT
    Args:
        session: Db instance session for retrieving user info
        authorization: The incoming JWT from cognito, passed via the frontend app
        if this is not supplied then None will be returned.
        When deployed the api is protected by the WAF, when testing locally this if fine
        logger: Structured logger instance
    Returns:
        tuple[User, StructuredLogger]: The user matching the username in the token and the logger
    """

    logger.debug("Authorization header {authorization}", authorization=authorization)

    if not authorization:
        logger.info("No token header found in get_current_user")
        raise HTTPException(
            status_code=401,
            detail="Unauthorised",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.debug("Auth from token: {authorization}", authorization=authorization)

    try:
        email = get_authorised_user(authorization, logger)

        # We have decided not to check Keycloak roles (any role is allowed)

        statement = select(User).where(User.email == email)
        if user := session.exec(statement).one_or_none():
            logger.set_context_field("user_email", str(user))
            return user

        logger.info("User not found with email {email}, creating", email=str(user))
        user = User(email=email)
        session.add(user)
        session.commit()
        session.refresh(user)
        logger.set_context_field("user_email", str(user))
        # TODO: Update user roles if needed here
        return user

    except Exception as e:
        logger.exception("An error occurred during user authorisation")
        raise HTTPException(status_code=401) from e

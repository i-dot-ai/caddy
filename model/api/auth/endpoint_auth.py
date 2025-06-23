import logging
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlmodel import Session, select

from api.auth.token_auth import parse_auth_token
from api.environment import config, get_session
from api.models import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_current_user(
    session: Annotated[Session, Depends(get_session)],
    authorization: Annotated[str, Header()] = None,
) -> User | None:  # noqa: RUF013, PLR0912, C901
    """
    Called on every endpoint to decode JWT in every request header under the name "Authorization"
    Gets or creates the user based on the email in the JWT
    Args:
        session: Db instance session for retrieving user info
        authorization: The incoming JWT from cognito, passed via the frontend app
        if this is not supplied then None will be returned.
        When deployed the api is protected by the WAF, when testing locally this if fine
    Returns:
        User: The user matching the username in the token
    """

    logger.info(f"Authorization header {authorization}")

    if not authorization:
        logger.info("No token header found in get_current_user")
        raise HTTPException(
            status_code=401,
            detail="Unauthorised",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.debug("Auth from token: %s", authorization)

    try:
        email, role_names = parse_auth_token(authorization)

        if config.app_name not in role_names:
            logger.info("User %s does not have the required role", email)
            raise HTTPException(
                status_code=401,
                detail="Unauthorised",
                headers={"WWW-Authenticate": "Bearer"},
            )

        statement = select(User).where(User.email == email)
        if user := session.exec(statement).one_or_none():
            return user

        logger.info("User not found with email %s, creating", email)
        user = User(email=email)
        session.add(user)
        session.commit()
        session.refresh(user)
        # TODO: Update user roles if needed here
        return user

    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=401) from e

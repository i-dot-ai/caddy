import os
from logging import getLogger

import click
from sqlmodel import Session, select

from api.environment import config
from api.models import User

logger = getLogger(__file__)


@click.command()
def initialize_admin_users():
    """initialize admin users from environment variable"""
    with Session(config.get_database()) as session:
        for admin_user in os.environ.get("ADMIN_USERS", "").split(","):
            email = admin_user.strip()
            if user := session.exec(
                select(User).where(User.email == email)
            ).one_or_none():
                user.is_admin = True
                logger.info("setting %s to admin", email)
            else:
                user = User(email=email, is_admin=True)
                logger.info("creating %s as admin", email)

            session.add(user)
        session.commit()


if __name__ == "__main__":
    initialize_admin_users()

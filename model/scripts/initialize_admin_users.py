from logging import getLogger

import click
from sqlmodel import Session, select

from api.data_structures.models import User
from api.environments.environment import config

logger = getLogger(__file__)


logger.info("running admin user script")


@click.command()
def initialize_admin_users():
    """initialize admin users from environment variable"""
    with Session(config.get_database()) as session:
        for admin_user in config.admin_users:
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

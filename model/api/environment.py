import os

from dotenv import load_dotenv
from sqlmodel import Session

if os.environ.get("ENVIRONMENT", "local") == "local":
    load_dotenv()
    from api.environments.local import config
elif os.environ["ENVIRONMENT"] == "test":
    load_dotenv("../.env.test", override=True)
    from api.environments.test import config
elif os.environ["ENVIRONMENT"].upper() in ("DEV", "PREPROD", "PROD"):
    from api.environments.production import config  # noqa
else:
    raise ValueError("ENVIRONMENT is miss-configured")


def get_session():
    with Session(config.get_database()) as session:
        yield session

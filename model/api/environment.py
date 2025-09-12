import os
from functools import lru_cache

from dotenv import load_dotenv
from sqlmodel import Session

from api.config import CaddyConfig

if os.environ.get("ENVIRONMENT", "local").upper() == "LOCAL":
    load_dotenv()
    from api.environments.local import config
elif os.environ["ENVIRONMENT"].upper() == "TEST":
    load_dotenv("../.env.test", override=True)
    from api.environments.test import config
elif os.environ["ENVIRONMENT"].upper() in ("DEV", "PREPROD", "PROD"):
    from api.environments.production import config  # noqa
else:
    raise ValueError("ENVIRONMENT is miss-configured")


@lru_cache
def get_config() -> CaddyConfig:
    return config


def get_session():
    with Session(config.get_database()) as session:
        yield session

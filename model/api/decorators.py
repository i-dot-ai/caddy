import functools
from inspect import signature
from typing import Callable, Optional

from fastapi.requests import Request
from i_dot_ai_utilities.logging.types.enrichment_types import ContextEnrichmentType

from api.environment import config
from api.models import User


def with_logger(logger_name: Optional[str] = None):
    """
    Decorator that injects a logger into sync route functions and refreshes context before handing back.

    Args:
        logger_name: Optional name for the logger. If not provided, uses the function name.

    Usage:
        @router.get("/example")
        @with_logger("my_route")
        def my_route(logger, other_params...):
            logger.info("Route called")
            return {"message": "success"}
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            log_name = logger_name or func.__name__
            logger = config.get_logger(log_name)
            request: Request | None = kwargs.get("request", None)
            user: User | None = kwargs.get("user", None)
            user_id = user.id if user else "Unknown"
            user_email = user.email if user else "Unknown"
            logger.refresh_context(
                context_enrichers=[
                    {
                        "type": ContextEnrichmentType.FASTAPI,
                        "object": request,
                        "user_id": user_id,
                        "user_email": user_email,
                    }
                ]
            )
            logger.info(
                "Request to {url_path} by user {user}",
                url_path=request.url.path,
                user=user_id,
            )
            sig = signature(func)
            if "logger" in sig.parameters:
                kwargs["logger"] = logger
            return func(*args, **kwargs)

        return wrapper

    return decorator

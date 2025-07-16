from fastapi import Depends
from fastapi.requests import Request
from i_dot_ai_utilities.logging.types.enrichment_types import ContextEnrichmentType

from api.auth import get_current_user
from api.environment import config
from api.models import User


def get_logger(logger_name: str = None):
    def _get_logger(request: Request, user: User = Depends(get_current_user)):
        log_name = logger_name or "default"
        logger = config.get_logger(log_name)
        user_id = user.id if user else "Unknown"
        user_email = user.email if user else "Unknown"

        logger.refresh_context(
            context_enrichers=[
                {
                    "type": ContextEnrichmentType.FASTAPI,
                    "object": request,
                }
            ]
        )
        logger.set_context_field("user_email", user_email)
        logger.set_context_field("user_id", user_id)
        logger.info(
            "Request to {url_path} by user {user}",
            url_path=request.url.path,
            user=user_id,
        )
        return logger

    return _get_logger

from fastapi.requests import Request
from i_dot_ai_utilities.logging.types.enrichment_types import ContextEnrichmentType

from api.environments.environment import config


def get_logger(logger_name: str = None):
    def _get_logger(request: Request):
        log_name = logger_name or "default"
        logger = config.get_logger(log_name)
        if config.env.upper() not in ["LOCAL", "TEST"]:
            logger.refresh_context(
                context_enrichers=[
                    {
                        "type": ContextEnrichmentType.FASTAPI,
                        "object": request,
                    }
                ]
            )
        return logger

    return _get_logger

import contextlib
import logging
import time
from typing import Annotated, AsyncIterator, Callable

import sentry_sdk
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from langchain.schema import Document
from sqlmodel import Session, select
from starlette.applications import Starlette

from api.environment import config, get_session
from api.mcp_app import (
    handle_streamable_http,
    session_manager,
)
from api.models import Collection
from api.rest_app import router
from api.search import search_collection
from api.types import QueryRequest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if config.sentry_dsn:
    sentry_sdk.init(config.sentry_dsn, environment=config.env)


@contextlib.asynccontextmanager
async def lifespan(
    _: Starlette,
) -> AsyncIterator[None]:
    """Context manager for session manager."""
    async with session_manager.run():
        logger.info("Application started with StreamableHTTP session manager!")
        try:
            yield
        finally:
            logger.info("Application shutting down...")


app = FastAPI(
    title="Caddy Model API",
    description="API for CRUD and search operations",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)

# Add MCP sub-app
app.mount("/search", app=handle_streamable_http)


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add trusted host middleware
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=["*"]
)  # Configure with your domains


@app.middleware("http")
async def log_requests(request: Request, call_next: Callable):
    if request.url.path == "/healthcheck":
        return await call_next(request)
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    logger.info(
        f"Method: {request.method} Path: {request.url.path} Duration: {duration:.2f}s"
    )
    return response


@app.get("/healthcheck")
async def health_check():
    return {"status": "caddy is healthy"}


@app.post("/search")
async def query_endpoint(
    request: QueryRequest,
    session: Annotated[Session, Depends(get_session)],
) -> list[Document]:
    """Query endpoint for the Caddy Model.

    Args:
        request (QueryRequest): The query request containing:
            - query (str): The query text
            - index_name (str): The name of the OpenSearch index to search

    Returns:
        dict: OpenSearch response containing search results
    """
    statement = (
        select(Collection)
        .where(Collection.name == request.collection_name)
        .order_by(Collection.created_at)
    )
    collection = session.exec(statement).one_or_none()

    if not collection:
        raise HTTPException(
            status_code=404, detail=f"Collection {request.collection_name} not found"
        )

    try:
        return await search_collection(
            collection.id,
            request.query,
        )

    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500)

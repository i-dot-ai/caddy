import contextlib
import time
from typing import Annotated, AsyncIterator, Callable

import sentry_sdk
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from langchain.schema import Document
from sqlalchemy import text
from sqlmodel import Session, select
from starlette.applications import Starlette

from api.data_structures.models import Collection
from api.data_structures.types import QueryRequest
from api.embeddings.search import search_collection
from api.environments.environment import config, get_session
from api.mcp.mcp_app import (
    handle_streamable_http,
    session_manager,
)
from api.rest_api.collections import router as collections_router
from api.rest_api.resources import router as resources_router

logger = config.get_logger(__name__)

if config.sentry_dsn:
    sentry_sdk.init(config.sentry_dsn, environment=config.env)

db_client = config.get_database()


@contextlib.asynccontextmanager
async def lifespan(
    _: Starlette,
) -> AsyncIterator[None]:
    """Context manager for session manager."""
    async with session_manager.run():
        logger.info("Application started with StreamableHTTP session manager!")

        try:
            client = await config.get_qdrant_client()
            sync_client = config.get_sync_qdrant_client()
            await client.get_collections()
            await client.collection_exists(config.qdrant_collection_name)
            sync_client.get_collections()
        except Exception as e:
            logger.exception("Qdrant connection validation failed")
            raise RuntimeError(f"Failed to connect to qdrant: {e}")
        else:
            logger.info("Qdrant successfully connected")
            await config.initialize_qdrant_collections()
            try:
                engine = db_client
                with engine.connect() as connection:
                    connection.execute(text("SELECT 1"))
                logger.info("Database connection validated successfully!")
            except Exception as e:
                logger.exception("Database connection validation failed")
                raise RuntimeError(f"Failed to connect to database: {e}")
            else:
                try:
                    yield
                finally:
                    logger.info("Application shutting down...")
                    await config.close_qdrant_client()
                    config.close_sync_qdrant_client()


app = FastAPI(
    title="Caddy Model API",
    description="API for CRUD and search operations",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(collections_router)
app.include_router(resources_router)

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
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])


@app.exception_handler(404)
async def not_found_handler(request: Request, _):
    logger.warning("Page not found")
    return JSONResponse(
        status_code=404,
        content={"message": "Not found"},
    )


@app.middleware("http")
async def log_requests(request: Request, call_next: Callable):
    logger.refresh_context()
    if request.url.path == "/healthcheck":
        return await call_next(request)
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    logger.info(
        "Method: {request_method} Path: {url_path} Duration: {duration}s",
        request_method=request.method,
        url_path=request.url.path,
        duration=round(duration, 2),
    )
    return response


@app.get("/healthcheck")
async def health_check():
    return {"status": "ok", "sha": config.git_sha}


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
    logger.refresh_context()
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
        return await search_collection(collection.id, request.query, session=session)

    except Exception:
        logger.exception(
            "An error occurred when searching collection {collection_name}",
            collection_name=collection.name,
        )
        raise HTTPException(status_code=500)

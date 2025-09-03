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

from api.environment import config, get_session
from api.mcp_app import create_collection_handler
from api.models import Collection
from api.rest_app import router
from api.search import search_collection
from api.types import QueryRequest

# Configure logging
logger = config.get_logger(__name__)

if config.sentry_dsn:
    sentry_sdk.init(config.sentry_dsn, environment=config.env)

db_client = config.get_database()

session_managers = []


@contextlib.asynccontextmanager
async def lifespan(
    _: Starlette,
) -> AsyncIterator[None]:
    """Context manager for session managers."""

    # Start all session managers
    session_manager_contexts = []
    for session_manager in session_managers:
        context = session_manager.run()
        await context.__aenter__()
        session_manager_contexts.append(context)

    logger.info(
        f"Application started with {len(session_managers)} StreamableHTTP session managers!"
    )

    try:
        engine = db_client
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        logger.info("Database connection validated successfully!")
    except Exception as e:
        logger.exception("Database connection validation failed")
        raise RuntimeError(f"Failed to connect to database: {e}")

    try:
        yield
    finally:
        logger.info("Application shutting down...")
        # Shutdown all session managers
        for context in reversed(session_manager_contexts):
            await context.__aexit__(None, None, None)


# Create the FastAPI app first
app = FastAPI(
    title="Caddy Model API",
    description="API for CRUD and search operations",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)

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

# Setup collection handlers after app is created
with Session(db_client) as connection:
    statement = select(Collection)
    all_collections = connection.exec(statement).all()
    for collection in all_collections:
        handler, session_manager = create_collection_handler(collection.slug)
        session_managers.append(session_manager)
        app.mount(f"/{collection.slug}", app=handler)


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

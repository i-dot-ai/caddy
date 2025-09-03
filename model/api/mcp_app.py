import contextlib
import contextvars
from datetime import UTC, datetime
from typing import Iterator

from fastapi import HTTPException
from i_dot_ai_utilities.logging.structured_logger import StructuredLogger
from i_dot_ai_utilities.logging.types.enrichment_types import ContextEnrichmentType
from langchain_core.documents import Document
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select
from starlette.requests import Request
from starlette.types import Receive, Scope, Send

from api.auth import get_authorised_user
from api.environment import config
from api.models import Collection, User, UserCollection
from api.search import search_collection

logger = config.get_logger(__name__)
metric_writer = config.get_metrics_writer()
KEYCLOAK_ALLOWED_ROLES = config.keycloak_allowed_roles

# Context variable to store current user email
_current_user_email: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_user_email", default=None
)


@contextlib.asynccontextmanager
async def current_user_email(value: EmailStr) -> Iterator[None]:
    """Context manager to set the current-user-email"""
    token = _current_user_email.set(value)
    try:
        yield
    finally:
        _current_user_email.reset(token)


class ToolResponse(BaseModel):
    documents: list[Document]


def __validate_user_access(
    request: Request, struct_logger: StructuredLogger
) -> EmailStr | None:
    if config.env == "LOCAL":
        if config.admin_users:
            return config.admin_users[0]
        raise ValueError("local env selected but no ADMIN_USERS set")

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        struct_logger.info("auth_header not found")
        return None

    token = auth_header.removeprefix("Bearer ")
    authorised_user = get_authorised_user(token, logger=struct_logger)
    if not authorised_user:
        struct_logger.info(
            "user not authorised for roles: {roles}", roles=KEYCLOAK_ALLOWED_ROLES
        )
        return None
    return authorised_user


def get_current_user() -> EmailStr:
    if user_email := _current_user_email.get():
        return user_email
    raise HTTPException(401, detail="Authentication required")


def create_collection_handler(collection_slug: str):
    """Factory function to create a handler for a specific collection"""

    # Create a single MCP server for this collection
    mcp_server = Server(f"Caddy MCP server - {collection_slug}")

    @mcp_server.call_tool()
    async def call_tool(
        _: str,
        arguments: dict,
    ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        logger.refresh_context()
        call_tool_start = datetime.now(UTC)
        metric_writer.put_metric(
            metric_name="tool_call_count",
            value=1,
            dimensions={
                "tool_name": collection_slug,
                "collection": collection_slug,
            },
        )

        user_email = get_current_user()

        logger.info(
            "Calling tool {name} with args {arguments} by user {user_email} for collection {collection_slug}",
            name=collection_slug,
            arguments=arguments,
            user_email=user_email,
            collection_slug=collection_slug,
        )

        with Session(config.get_database()) as session:
            # Check if user has access to this specific collection
            statement = (
                select(UserCollection)
                .join(User)
                .join(Collection)
                .where(
                    User.email == user_email,
                )
            )
            user_collections = session.exec(statement).all()
            user_collection = next(
                filter(
                    lambda uc: uc.collection.slug == collection_slug,
                    user_collections,
                ),
                None,
            )

            if not user_collection:
                raise HTTPException(
                    403, detail="User does not have access to this collection"
                )

            documents = await search_collection(
                user_collection.collection_id,
                query=arguments.get("query"),
                keywords=arguments.get("keywords", []),
                session=session,
            )

        tool_call_end = datetime.now(UTC)
        timer_result_ms = (tool_call_end - call_tool_start).total_seconds() * 1000
        metric_writer.put_metric(
            metric_name="tool_call_duration_ms",
            value=timer_result_ms,
            dimensions={
                "tool_name": collection_slug,
                "collection": collection_slug,
            },
        )
        return [
            types.TextContent(
                type="text",
                text=ToolResponse(documents=documents).model_dump_json(),
            )
        ]

    @mcp_server.list_tools()
    async def list_tools() -> list[types.Tool]:
        user_email = get_current_user()

        logger.refresh_context()
        logger.info(
            "Listing tools for user: {user_email} for collection {collection_slug}",
            user_email=user_email,
            collection_slug=collection_slug,
        )

        with Session(config.get_database()) as session:
            # Get the specific collection this endpoint represents
            statement = (
                select(UserCollection)
                .join(User)
                .join(Collection)
                .where(
                    User.email == user_email,
                )
            )
            user_collections = session.exec(statement).all()
            chosen_user_collection = next(
                filter(
                    lambda user_collection: user_collection.collection.slug
                    == collection_slug,
                    user_collections,
                ),
                None,
            )

            if not chosen_user_collection:
                logger.info(
                    "User {user_email} does not have access to collection {collection_slug}",
                    user_email=user_email,
                    collection_slug=collection_slug,
                )
                return []

        # Return a single tool called "call_tool"
        return [
            types.Tool(
                name=chosen_user_collection.collection.name,
                description=chosen_user_collection.collection.description,
                inputSchema={
                    "type": "object",
                    "required": ["query", "keywords"],
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "What do you want to search for?",
                        },
                        "keywords": {
                            "type": "array",
                            "description": (
                                "Extract 3-5 specific terms that capture key issues or needs. "
                                "Include amounts, dates, or specific services mentioned. "
                                "Focus on actionable terms that could help find relevant documents. "
                                "Avoid generic words or category names."
                            ),
                            "items": {"type": "string"},
                        },
                    },
                },
                annotations={
                    "title": f"Search {chosen_user_collection.collection.name}"
                },
            )
        ]

    # Create session manager for this server
    session_manager = StreamableHTTPSessionManager(
        app=mcp_server,
        event_store=None,
        json_response=True,
        stateless=True,
    )

    async def handle_collection_http(
        scope: Scope, receive: Receive, send: Send
    ) -> None:
        request = Request(scope, receive)
        logger.refresh_context(
            context_enrichers=[
                {
                    "type": ContextEnrichmentType.FASTAPI,
                    "object": request,
                }
            ]
        )
        user_email = __validate_user_access(request, logger)
        if not user_email:
            logger.info(
                "User not authorized for collection {collection_slug}",
                collection_slug=collection_slug,
            )
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        [b"content-type", b"text/plain"],
                    ],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b"Not Found",
                }
            )
            return

        # Set user email in context for the duration of this request
        async with current_user_email(user_email):
            await session_manager.handle_request(scope, receive, send)

    return handle_collection_http, session_manager

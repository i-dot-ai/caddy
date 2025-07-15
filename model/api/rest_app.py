from datetime import timedelta
from io import BytesIO
from logging import getLogger
from typing import Annotated
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from markitdown import MarkItDown, MarkItDownException
from sqlalchemy import func
from sqlmodel import Session, select

from api.auth import get_current_user
from api.environment import config, get_session
from api.models import (
    Collection,
    CollectionResources,
    Resource,
    TextChunk,
    User,
    UserCollection,
    UserCollectionWithEmail,
    UserRoleList,
    utc_now,
)
from api.scrape import Scraper
from api.types import (
    Chunks,
    CollectionBase,
    CollectionDto,
    CollectionsDto,
    Role,
    UserRole,
)

router = APIRouter()  # Create an APIRouter instance
md = MarkItDown()
logger = getLogger(__file__)
metric_writer = config.get_metrics_writer()


def _split_text(text: str) -> list[Document]:
    """
    Split text into chunks using RecursiveCharacterTextSplitter.

    Args:
        text (str): The text to chunk.

    Returns:
        List[Document]: A list of Documents.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2048,
        chunk_overlap=100,
        length_function=len,
    )
    document = Document(text)
    return text_splitter.split_documents([document])


def __check_user_is_member_of_collection(
    user: User | None,
    collection_id: UUID,
    session: Session,
    is_manager: bool = True,
):
    if user is None:
        logger.info("Anonymous access request for collection % denied", collection_id)
        raise HTTPException(status_code=401, detail="Unauthorised")

    if not session.get(Collection, collection_id):
        logger.info("Collection not found for route request for user %".format())
        raise HTTPException(status_code=404, detail="Collection Not Found")

    if user.is_admin:
        logger.info(
            "user % has access to %s as they are an admin", user.email, collection_id
        )
        return

    user_collection = session.get(
        UserCollection, {"user_id": user.id, "collection_id": collection_id}
    )

    if not user_collection:
        logger.info("User % not allowed to see collection %s".format())
        raise HTTPException(
            status_code=403, detail="User is not a member of this collection"
        )

    if is_manager and user_collection.role != Role.MANAGER:
        logger.info(
            "User % must be a manager for this request to see collection %s".format()
        )
        raise HTTPException(
            status_code=403, detail="User is not a manger of this collection"
        )

    logger.info(
        "user % has access to %s as they are a %s",
        user.email,
        collection_id,
        user_collection.role,
    )


def __process_resource(
    resource_name: str,
    collection_id: UUID,
    content_type: str,
    content: str | bytes,
    session: Session,
    user: User,
    url: str | None = None,
) -> tuple[Resource, timedelta]:
    process_time_start = utc_now()
    resource = Resource(
        collection_id=collection_id,
        filename=resource_name,
        content_type=content_type,
        url=url,
        created_by=user,
    )
    session.add(resource)
    session.commit()
    session.refresh(resource)

    if not url and type(content) is bytes:
        # Assume the file is a File, not URL, so it can be uploaded to S3
        # Take advantage of S3 upload and download to handle file conversion and to get back string body
        config.s3_client.put_object(
            Bucket=config.data_s3_bucket,
            Key=f"{config.s3_prefix}/{collection_id}/{resource.id}/{resource_name}",
            Body=content,
        )
        s3_object = config.s3_client.get_object(
            Bucket=config.data_s3_bucket,
            Key=f"{config.s3_prefix}/{resource.collection_id}/{resource.id}/{resource.filename}",
        )

        s3_content = BytesIO(s3_object["Body"].read())
        content = md.convert(s3_content).text_content

    documents = _split_text(content)

    embeddings = config.embedding_model.embed_documents(
        [d.page_content for d in documents]
    )

    for order, (document, embedding) in enumerate(zip(documents, embeddings)):
        text_chunk = TextChunk(
            text=document.page_content,
            order=order,
            resource=resource,
            embedding=embedding,
        )
        session.add(text_chunk)
    resource.is_processed = True
    resource.process_time = utc_now() - process_time_start
    session.add(resource)
    session.commit()

    return resource, (utc_now() - process_time_start)


@router.get(
    "/collections/{collection_id}/resources", status_code=200, tags=["collections"]
)
def get_collection_resources(
    collection_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
) -> CollectionResources:
    """returns a list of resources belonging to this collection"""
    __check_user_is_member_of_collection(user, collection_id, session, is_manager=False)

    if not session.get(Collection, collection_id):
        raise HTTPException(status_code=404)

    resources_statement = (
        select(Resource)
        .where(Resource.collection_id == collection_id)
        .order_by(Resource.filename)
        .offset(page_size * (page - 1))
        .limit(page_size)
    )
    resources = session.exec(resources_statement).all()

    count_statement = select(func.count(Resource.id)).where(
        Resource.collection_id == collection_id
    )
    total = session.scalar(count_statement)

    return CollectionResources(
        collection_id=collection_id,
        page=page,
        total=total,
        page_size=page_size,
        resources=resources,
    )


@router.post("/collections", status_code=201, tags=["collections"])
def create_collection(
    new_collection: CollectionBase,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Collection:
    """create a collection"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="User needs to be an admin")

    collection = Collection(**new_collection.model_dump())
    stmt = select(Collection).where(Collection.name == collection.name)
    results = session.exec(stmt).all()
    if results:
        raise HTTPException(
            status_code=422, detail="A collection with this name already exists"
        )
    session.add(collection)
    session.commit()
    session.refresh(collection)

    user_collection = UserCollection(
        user_id=user.id,
        collection_id=collection.id,
        role=Role.MANAGER,
    )
    session.add(user_collection)
    session.commit()
    session.refresh(collection)

    return collection


@router.put("/collections/{collection_id}", status_code=200, tags=["collections"])
def update_collection(
    collection_id: UUID,
    collection_details: CollectionBase,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> CollectionDto:
    """update a collection"""
    if collection := session.get(Collection, collection_id):
        collection.name = collection_details.name
        collection.description = collection_details.description
        session.add(collection)
        session.commit()
        session.refresh(collection)

        is_manager = False
        if user:
            is_manager = (
                session.scalar(
                    select(func.count(UserCollection.user_id)).where(
                        UserCollection.collection_id == collection.id,
                        UserCollection.user_id == user.id,
                        UserCollection.role == Role.MANAGER,
                    )
                )
                > 0
            )

        return CollectionDto(
            id=collection.id,
            name=collection.name,
            description=collection.description,
            created_at=collection.created_at,
            is_manager=is_manager,
        )

    raise HTTPException(status_code=404)


@router.delete("/collections/{collection_id}", status_code=200, tags=["collections"])
def delete_collection(
    collection_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> UUID:
    """delete a collection"""
    __check_user_is_member_of_collection(user, collection_id, session)

    objects = config.s3_client.list_objects_v2(
        Bucket=config.data_s3_bucket, Prefix=f"{config.s3_prefix}/{collection_id}"
    )
    if contents := objects.get("Contents"):
        object_keys = [{"Key": obj["Key"]} for obj in contents]
        config.s3_client.delete_objects(
            Bucket=config.data_s3_bucket, Delete={"Objects": object_keys}
        )

    if collection := session.get(Collection, collection_id):
        session.delete(collection)
        session.commit()
        return collection_id

    raise HTTPException(status_code=404)


@router.post(
    "/collections/{collection_id}/resources", status_code=201, tags=["resources"]
)
async def create_resource(
    collection_id: UUID,
    file: Annotated[UploadFile, File(...)],
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> Resource:
    """
    Endpoint to upload a file to a specified collection.

    Args:
        session: DB session
        user: The logged-in user from auth JWT or None
        collection_id (str): The collection to upload the file to.
        file (Annotated[UploadFile, File()]): The file being uploaded.

    Returns:
        Resource
    """
    __check_user_is_member_of_collection(user, collection_id, session)

    try:
        resource, processing_time = __process_resource(
            resource_name=file.filename,
            collection_id=collection_id,
            content_type=file.content_type,
            content=file.file.read(),
            session=session,
            user=user,
            url=None,
        )
    except MarkItDownException:
        raise HTTPException(
            status_code=422, detail="An issue occurred processing this file"
        )
    except Exception:
        raise HTTPException(
            status_code=422, detail="An issue occurred processing this file"
        )
    else:
        session.commit()
        session.refresh(resource)

        metric_writer.put_metric(
            metric_name="resource_created",
            value=1,
            dimensions={
                "file_type": resource.content_type,
            },
        )
        metric_writer.put_metric(
            metric_name="resource_created_duration_ms",
            value=(processing_time).total_seconds() * 1000,
            dimensions={
                "file_type": resource.content_type,
            },
        )
        metric_writer.put_metric(
            metric_name="resource_created_size_bytes",
            value=file.size,
            dimensions={
                "file_type": resource.content_type,
            },
        )

        return resource


@router.post(
    "/collections/{collection_id}/resources/urls", status_code=201, tags=["resources"]
)
async def create_resources_from_url_list(
    collection_id: UUID,
    urls: list[str],
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[Resource]:
    """
    Endpoint to upload a file to a specified collection.

    Args:
        session: DB session
        user: The logged-in user from auth JWT or None
        collection_id (str): The collection to upload the file to.
        urls (list[str]): The urls being uploaded.

    Returns:
        Resources
    """
    __check_user_is_member_of_collection(user, collection_id, session)
    scrape_time_start = utc_now()
    # urls = url_list.urls
    for url in urls:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise HTTPException(
                status_code=422, detail=f"Unsupported URL ({url}) found in URL list"
            )

    scraper = Scraper()
    files = await scraper.download_urls(urls)
    scrape_processing_time = utc_now() - scrape_time_start
    try:
        resources = []
        processing_total = timedelta()
        for file in files:
            resource, resource_processing_time = __process_resource(
                url=file.url,
                resource_name=file.title,
                collection_id=collection_id,
                content_type=file.content_type,
                content=file.markdown,
                session=session,
                user=user,
            )
            session.add(resource)
            session.commit()
            resources.append(resource)
            processing_total += resource_processing_time
        logger.info("Finished scraping from urls")
        for resource in resources:
            session.refresh(resource)
        metric_writer.put_metric(
            metric_name="resource_created_from_url_call_count",
            value=1,
        )
        metric_writer.put_metric(
            metric_name="resource_from_urls_created_duration_ms_total",
            value=(scrape_processing_time + processing_total).total_seconds() * 1000,
        )
        return resources
    except Exception as e:
        logger.error(f"Error uploading urls: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to upload resources")


@router.get(
    "/collections/{collection_id}/resources/{resource_id}/documents",
    status_code=200,
    tags=["resources"],
)
def get_resource_documents(
    collection_id: UUID,
    resource_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
) -> Chunks:
    """get a documents belonging to a resource"""

    __check_user_is_member_of_collection(user, collection_id, session, is_manager=False)

    if not session.get(Resource, resource_id):
        raise HTTPException(status_code=404)

    statement = (
        select(TextChunk)
        .where(TextChunk.resource_id == resource_id)
        .order_by(TextChunk.order)
        .offset(page_size * (page - 1))
        .limit(page_size)
    )

    text_chunks = session.exec(statement).all()

    def to_document(tc: TextChunk):
        return Document(
            page_content=tc.text,
            id=str(tc.id),
            metadata={
                "resource_id": tc.resource_id,
                "filename": tc.resource.filename,
                "content_type": tc.resource.content_type,
                "chunk_order": tc.order,
                "created_at": tc.created_at,
            },
        )

    documents = [to_document(item) for item in text_chunks]

    count_statement = select(func.count(TextChunk.id)).where(
        TextChunk.resource_id == resource_id
    )
    total = session.exec(count_statement).one()

    return Chunks(
        collection_id=collection_id,
        resource_id=resource_id,
        page=page,
        total=total,
        page_size=page_size,
        documents=documents,
    )


@router.delete(
    "/collections/{collection_id}/resources/{resource_id}",
    status_code=200,
    tags=["resources"],
)
def delete_resource(
    collection_id: UUID,
    resource_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    """delete a resource"""
    __check_user_is_member_of_collection(user, collection_id, session)

    config.s3_client.delete_object(
        Bucket=config.data_s3_bucket,
        Key=f"{config.s3_prefix}/{collection_id}/{resource_id}",
    )

    if resource := session.get(Resource, resource_id):
        session.delete(resource)
        session.commit()
    else:
        raise HTTPException(status_code=404)


@router.get(
    "/collections/{collection_id}/resources/{resource_id}",
    status_code=200,
    tags=["resources"],
)
def get_resource(
    collection_id: UUID,
    resource_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> Resource:
    """get a resource"""
    __check_user_is_member_of_collection(user, collection_id, session, is_manager=False)

    if resource := session.get(Resource, resource_id):
        return resource
    raise HTTPException(status_code=404)


@router.get("/collections", status_code=200, tags=["collections"])
def get_collections(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
) -> CollectionsDto:
    """Get a list of all available collections.
    Args:
        session: DB session
        user: Logged-in user or none from JWT
        page: Page number
        page_size: Number of records for each page
    Returns:
        CollectionList: List of available collections available to currently logged-in user
    Raises:
        HTTPException: 500 status code if collection retrieval fails
    """
    logger.info("Getting collections for user: {user}".format(user=user.email))
    try:
        where_clauses = (
            [UserCollection.user_id == user.id] if user and not user.is_admin else []
        )

        is_manager = func.coalesce(
            func.bool_or(UserCollection.role == Role.MANAGER).over(
                partition_by=Collection.id
            ),
            False,
        ).label("is_manager")

        statement = (
            select(Collection, is_manager)
            .join(UserCollection, isouter=True)
            .where(*where_clauses)
            .distinct()
            .order_by(Collection.id)
            .offset(page_size * (page - 1))
            .limit(page_size)
        )
        count_statement = select(func.count(Collection.id))
        query_results = session.exec(statement).all()

        # Build collections based on previous statements
        collections = [
            CollectionDto(
                id=collection.id,
                name=collection.name,
                description=collection.description,
                created_at=collection.created_at,
                is_manager=bool(is_manager),
            )
            for collection, is_manager in query_results
        ]

        total = session.exec(count_statement).one()

        return CollectionsDto(
            total=total,
            page=page,
            page_size=page_size,
            collections=collections,
            is_admin=user.is_admin if user else False,
        )
    except Exception as e:
        logger.error(f"Error retrieving available indexes: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve available collections"
        )


@router.get("/collections/{collection_id}/users", status_code=200, tags=["user-roles"])
def get_collections_user_roles(
    collection_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
) -> UserRoleList:
    __check_user_is_member_of_collection(user, collection_id, session)

    statement = (
        select(UserCollection, User.email.label("user_email"))
        .where(UserCollection.collection_id == collection_id)
        .join(User, UserCollection.user_id == User.id)
        .order_by(UserCollection.created_at)
        .offset(page_size * (page - 1))
        .limit(page_size)
    )
    user_roles = session.exec(statement).all()

    user_roles_with_emails: list[UserCollectionWithEmail] = [
        UserCollectionWithEmail(user_email=email, **ur.model_dump())
        for ur, email in user_roles
    ]

    count_statement = func.count(UserCollection.user_id)
    total = session.exec(count_statement).scalar()
    return UserRoleList(
        page=page, page_size=page_size, total=total, user_roles=user_roles_with_emails
    )


@router.post("/collections/{collection_id}/users", status_code=201, tags=["user-roles"])
def create_collections_user_role(
    collection_id: UUID,
    user_role: UserRole,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> UserCollection:
    __check_user_is_member_of_collection(user, collection_id, session)

    user = User.get_by_email(session, user_role.email)

    if not user:
        user = User(email=user_role.email)
        session.add(user)
        session.commit()
        session.refresh(user)

    if not session.get(Collection, collection_id):
        raise HTTPException(status_code=404, detail="Collection Not Found")

    if user_collection := session.get(
        UserCollection, {"collection_id": collection_id, "user_id": user.id}
    ):
        user_collection.role = user_role.role
    else:
        user_collection = UserCollection(
            collection_id=collection_id,
            user_id=user.id,
            role=user_role.role,
        )

    session.add(user_collection)
    session.commit()
    session.refresh(user_collection)
    return user_collection


@router.delete(
    "/collections/{collection_id}/users/{user_id}",
    status_code=200,
    tags=["user-roles"],
)
def delete_collections_user_role(
    collection_id: UUID,
    user_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> bool:
    __check_user_is_member_of_collection(user, collection_id, session)

    if user_role := session.get(
        UserCollection, {"collection_id": collection_id, "user_id": user_id}
    ):
        session.delete(user_role)
        session.commit()
        return True
    raise HTTPException(status_code=404)

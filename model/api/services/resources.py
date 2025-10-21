from datetime import timedelta
from io import BytesIO
from urllib.parse import urlparse
from uuid import UUID

from fastapi import File
from i_dot_ai_utilities.logging.structured_logger import StructuredLogger
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from markitdown import MarkItDown
from sqlalchemy import func
from sqlmodel import Session, select

from api.data_structures.enums import CollectionPermissionEnum, ResourcePermissionEnum
from api.data_structures.models import (
    Collection,
    Resource,
    TextChunk,
    User,
    UserCollection,
    utc_now,
)
from api.data_structures.types import (
    Chunks,
    CollectionResources,
    ResourceDto,
)
from api.environments.environment import config
from api.utilities.exceptions import (
    InvalidUrlFormatException,
    ItemNotFoundException,
    NoPermissionException,
)
from api.utilities.permissions import (
    check_user_is_member_of_collection,
    get_collection_permissions_for_user,
    get_resource_permissions_for_user,
)
from api.utilities.scrape import Scraper

metric_writer = config.get_metrics_writer()
md = MarkItDown()


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


def __process_resource(
    resource_name: str,
    collection_id: UUID,
    content_type: str,
    content: str | bytes,
    session: Session,
    user: User,
    logger: StructuredLogger,
    url: str | None = None,
) -> tuple[Resource, timedelta]:
    process_time_start = utc_now()
    existing_resource = None
    if url:
        statement = (
            select(Resource)
            .where(Resource.collection_id == collection_id)
            .where(Resource.url == url)
        )
        existing_resource = session.exec(statement).first()
    if existing_resource:
        resource = existing_resource
        resource.created_at = utc_now()
        resource.created_by = user
    else:
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
        logger.info(
            "Uploading file to filestore - {resource_id}", resource_id=resource.id
        )

        client = config.get_file_store_client()

        client.put_object(
            key=f"{collection_id}/{resource.id}/{resource_name}", data=content
        )

        s3_object = client.read_object(
            key=f"{collection_id}/{resource.id}/{resource_name}", as_text=False
        )

        s3_content = BytesIO(s3_object)
        content = md.convert(s3_content).text_content

        logger.info(
            "File uploaded to file store - {resource_id}", resource_id=resource.id
        )

    documents = _split_text(content)

    for order, document in enumerate(documents):
        text_chunk = TextChunk(
            text=document.page_content,
            order=order,
            resource_id=resource.id,
            resource=resource,
        )
        session.add(text_chunk)
    resource.is_processed = True
    resource.process_time = utc_now() - process_time_start
    session.add(resource)
    session.commit()

    return resource, (utc_now() - process_time_start)


def get_resources_by_collection_id(
    user: User,
    session: Session,
    collection_id: UUID,
    logger: StructuredLogger,
    page_size: int = 10,
    page: int = 1,
) -> CollectionResources:
    try:
        if collection := session.get(Collection, collection_id):
            check_user_is_member_of_collection(
                user,
                collection.id,
                session,
                is_manager_of_collection=False,
                struct_logger=logger,
            )
            permissions = get_collection_permissions_for_user(user, collection, session)
            if permissions is None or CollectionPermissionEnum.VIEW not in permissions:
                raise NoPermissionException(
                    "No permission to view resources on this collection", 401
                )
            resources_statement = (
                select(Resource)
                .where(Resource.collection_id == collection.id)
                .order_by(Resource.filename)
                .offset(page_size * (page - 1))
                .limit(page_size)
            )
            resources = session.exec(resources_statement).all()

            count_statement = select(func.count(Resource.id)).where(
                Resource.collection_id == collection.id
            )
            total = session.scalar(count_statement)

            logger.info(
                "Retrieved collection {collection_id} resources ({resource_count}) for user {user_email}",
                collection_id=collection.id,
                resource_count=total,
                user_email=str(user),
            )

            if session.get(
                UserCollection, {"collection_id": collection_id, "user_id": user.id}
            ):
                use_file_name = True
            else:
                use_file_name = False

            resource_dtos = []
            for resource in resources:
                resource = Resource.model_validate(resource)
                resource_dtos.append(
                    ResourceDto(
                        id=resource.id,
                        filename=resource.filename
                        if use_file_name
                        else str(resource.id),
                        created_at=resource.created_at,
                        content_type=resource.content_type,
                        permissions=get_resource_permissions_for_user(
                            user, resource, session
                        ),
                        url=resource.url,
                        is_processed=resource.is_processed,
                        process_error=resource.process_error,
                        process_time=resource.process_time,
                        created_by_id=resource.created_by_id,
                        collection_id=resource.collection_id,
                    )
                )

            return CollectionResources(
                collection_id=collection.id,
                page=page,
                total=total,
                page_size=page_size,
                resources=resource_dtos,
            )
        else:
            raise ItemNotFoundException("Collection not found", 403)
    except Exception:
        raise


def create_resource_from_file(
    user: User,
    collection_id: UUID,
    session: Session,
    logger: StructuredLogger,
    file: File,
) -> ResourceDto:
    check_user_is_member_of_collection(
        user, collection_id, session, struct_logger=logger
    )

    if collection := session.get(Collection, collection_id):
        permissions = get_collection_permissions_for_user(user, collection, session)
        if CollectionPermissionEnum.MANAGE_RESOURCES not in permissions:
            raise NoPermissionException(
                message="User does not have permission to manage resources for this collection",
                error_code=401,
            )

        resource, processing_time = __process_resource(
            resource_name=file.filename,
            collection_id=collection_id,
            content_type=file.content_type,
            content=file.file.read(),
            session=session,
            user=user,
            logger=logger,
            url=None,
        )
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
            value=processing_time.total_seconds() * 1000,
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

        logger.info(
            "Resource created from file upload. File name: {file_name}. File type: {file_type}. File size (bytes): {file_size}. User: {user_email}. Processing time (ms): {processing_time}.",
            file_name=file.filename,
            file_type=file.content_type,
            file_size=file.size,
            user_email=str(user),
            processing_time=processing_time,
        )
        if session.get(
            UserCollection, {"collection_id": collection_id, "user_id": user.id}
        ):
            file_name = resource.filename
        else:
            file_name = str(resource.id)
        return ResourceDto(
            id=resource.id,
            filename=file_name,
            created_at=resource.created_at,
            content_type=resource.content_type,
            permissions=get_resource_permissions_for_user(user, resource, session),
            url=resource.url,
            is_processed=resource.is_processed,
            process_error=resource.process_error,
            process_time=resource.process_time,
            created_by_id=resource.created_by_id,
            collection_id=resource.collection_id,
        )
    else:
        raise ItemNotFoundException(error_code=404, message="Collection not found")


async def create_resource_from_urls(
    user: User,
    session: Session,
    collection_id: UUID,
    logger: StructuredLogger,
    urls: list[str],
) -> list[ResourceDto]:
    check_user_is_member_of_collection(
        user, collection_id, session, struct_logger=logger
    )
    if collection := session.get(Collection, collection_id):
        permissions = get_collection_permissions_for_user(user, collection, session)
        if CollectionPermissionEnum.MANAGE_RESOURCES not in permissions:
            raise NoPermissionException(
                "User does not have permission to manage resources for this collection",
                error_code=401,
            )
        scrape_time_start = utc_now()
        for url in urls:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise InvalidUrlFormatException(
                    error_code=422, message=f"Unsupported URL ({url}) found in URL list"
                )

        scraper = Scraper(logger)
        files = await scraper.download_urls(urls)
        scrape_processing_time = utc_now() - scrape_time_start
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
                logger=logger,
            )
            session.add(resource)
            session.commit()
            session.refresh(resource)
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
        logger.info(
            "Resource created from url scrape. URl count: {url_count}. User: {user_email}. Processing time (ms): {processing_time}.",
            url_count=len(urls),
            user_email=str(user),
            processing_time=(scrape_processing_time + processing_total).total_seconds()
            * 1000,
        )

        if session.get(
            UserCollection, {"collection_id": collection_id, "user_id": user.id}
        ):
            use_file_name = True
        else:
            use_file_name = False

        resource_dtos = []
        for resource in resources:
            resource_dtos.append(
                ResourceDto(
                    id=resource.id,
                    filename=resource.filename if use_file_name else str(resource.id),
                    created_at=resource.created_at,
                    content_type=resource.content_type,
                    permissions=get_resource_permissions_for_user(
                        user, resource, session
                    ),
                    url=resource.url,
                    is_processed=resource.is_processed,
                    process_error=resource.process_error,
                    process_time=resource.process_time,
                    created_by_id=resource.created_by_id,
                    collection_id=resource.collection_id,
                )
            )
        return resource_dtos
    else:
        raise ItemNotFoundException(error_code=404, message="Collection not found")


def get_resource_download_url(
    collection_id: UUID,
    resource_id: UUID,
    session: Session,
    logger: StructuredLogger,
    user: User,
) -> str:
    resource = session.get(Resource, resource_id)
    collection = session.get(Collection, collection_id)

    if not resource:
        raise ItemNotFoundException(error_code=404, message="Resource not found")

    if not collection:
        raise ItemNotFoundException(error_code=404, message="Collection not found")

    collection_permissions = get_collection_permissions_for_user(
        user, collection, session
    )
    resource_permissions = get_collection_permissions_for_user(user, resource, session)

    if (
        CollectionPermissionEnum.VIEW not in collection_permissions
        or ResourcePermissionEnum.VIEW not in resource_permissions
    ):
        raise NoPermissionException(
            error_code=401, message="No permission to view documents for this resource"
        )

    s3_client = config.get_file_store_client()

    s3_url = s3_client.download_object_url(
        key=f"{collection.id}/{resource.id}/{resource.filename}",
        expiration=3600,
    )

    return s3_url


def get_documents_for_resource_by_id(
    user: User,
    collection_id: UUID,
    session: Session,
    logger: StructuredLogger,
    resource_id: UUID,
    page: int = 1,
    page_size: int = 10,
) -> Chunks:
    check_user_is_member_of_collection(
        user,
        collection_id,
        session,
        is_manager_of_collection=False,
        struct_logger=logger,
    )

    resource = session.get(Resource, resource_id)
    collection = session.get(Collection, collection_id)

    if not resource:
        raise ItemNotFoundException(error_code=404, message="Resource not found")

    if not collection:
        raise ItemNotFoundException(error_code=404, message="Collection not found")

    collection_permissions = get_collection_permissions_for_user(
        user, collection, session
    )
    resource_permissions = get_collection_permissions_for_user(user, resource, session)

    if (
        CollectionPermissionEnum.VIEW not in collection_permissions
        or ResourcePermissionEnum.VIEW not in resource_permissions
    ):
        raise NoPermissionException(
            error_code=401, message="No permission to view documents for this resource"
        )

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

    logger.info(
        "{total} document(s) for resource {resource_id} retrieved by user {user_email}",
        total=total,
        resource_id=resource_id,
        user_email=str(user),
    )

    return Chunks(
        collection_id=collection_id,
        resource_id=resource_id,
        page=page,
        total=total,
        page_size=page_size,
        documents=documents,
    )


def delete_resource_by_id(
    user: User,
    session: Session,
    collection_id: UUID,
    resource_id: UUID,
    logger: StructuredLogger,
) -> UUID:
    check_user_is_member_of_collection(
        user, collection_id, session, struct_logger=logger
    )

    if resource := session.get(Resource, resource_id):
        permissions = get_resource_permissions_for_user(user, resource, session)

        if ResourcePermissionEnum.DELETE not in permissions:
            raise NoPermissionException(
                error_code=401,
                message="No permission to delete documents for this resource",
            )

        client = config.get_file_store_client()
        client.delete_object(f"{collection_id}/{resource_id}/{resource.filename}")

        session.delete(resource)
        session.commit()
        logger.info("Resource {resource_id} deleted", resource_id=resource_id)
        return resource_id
    else:
        raise ItemNotFoundException(error_code=404, message="Resource not found")


def get_resource_by_id(
    user: User,
    session: Session,
    collection_id: UUID,
    resource_id: UUID,
    logger: StructuredLogger,
) -> ResourceDto:
    check_user_is_member_of_collection(
        user,
        collection_id,
        session,
        is_manager_of_collection=False,
        struct_logger=logger,
    )

    if resource := session.get(Resource, resource_id):
        permissions = get_resource_permissions_for_user(user, resource, session)
        if ResourcePermissionEnum.VIEW not in permissions:
            raise NoPermissionException(
                error_code=401, message="No permission to view this resource"
            )
        logger.info("Resource {resource_id} found ", resource_id=resource_id)
        resource_dto = Resource.model_validate(resource)

        if session.get(
            UserCollection, {"collection_id": collection_id, "user_id": user.id}
        ):
            use_file_name = True
        else:
            use_file_name = False

        download_url = None
        if not resource_dto.url:
            s3_client = config.get_file_store_client()

            s3_url = s3_client.download_object_url(
                key=f"{collection_id}/{resource.id}/{resource.filename}",
                expiration=3600,
            )

            download_url = s3_url

        return ResourceDto(
            id=resource_dto.id,
            filename=resource_dto.filename if use_file_name else str(resource_dto.id),
            created_at=resource_dto.created_at,
            content_type=resource_dto.content_type,
            permissions=permissions,
            url=resource_dto.url,
            download_url=download_url,
            is_processed=resource_dto.is_processed,
            process_error=resource_dto.process_error,
            process_time=resource_dto.process_time,
            created_by_id=resource_dto.created_by_id,
            collection_id=resource_dto.collection_id,
        )
    else:
        raise ItemNotFoundException(error_code=404, message="Resource not found")

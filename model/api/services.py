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

from api.enums import CollectionPermissionEnum, ResourcePermissionEnum
from api.environment import config
from api.exceptions import (
    DuplicateItemException,
    InvalidUrlFormatException,
    ItemNotFoundException,
    NoPermissionException,
)
from api.models import (
    Collection,
    CollectionResources,
    Resource,
    TextChunk,
    User,
    UserCollection,
    utc_now, UserRoleList, UserCollectionWithEmail,
)
from api.permissions import (
    check_user_is_member_of_collection,
    get_collection_permissions_for_user,
    get_resource_permissions_for_user,
    is_user_admin_user,
)
from api.scrape import Scraper
from api.types import (
    CollectionBase,
    CollectionDto,
    CollectionsDto,
    Role, Chunks, UserRole,
)

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


def get_resources_by_collection_id(
    user: User,
    session: Session,
    collection_id: UUID,
    logger: StructuredLogger,
    page_size: int = 10,
    page: int = 1,
) -> CollectionResources:
    if collection := session.get(Collection, collection_id):
        check_user_is_member_of_collection(
            user, collection.id, session, is_manager=False, struct_logger=logger
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
            "Retrieved collection {collection_id} resources ({resource_count}) for user {user_id}",
            collection_id=collection.id,
            resource_count=total,
            user_id=user.id,
        )

        for resource in resources:
            resource.permissions = get_resource_permissions_for_user(
                user, resource, session
            )

        return CollectionResources(
            collection_id=collection.id,
            page=page,
            total=total,
            page_size=page_size,
            resources=resources,
        )
    else:
        raise ItemNotFoundException("Collection not found", 403)


def create_new_collection(
    new_collection: CollectionBase,
    session: Session,
    user: User,
    logger: StructuredLogger,
) -> Collection:
    if not user.is_admin:
        logger.info(
            "User {user} tried to create a collection {collection_name} without being an admin",
            user=user.email,
            collection_name=new_collection.collection_name,
        )
        raise NoPermissionException(error_code=403, message="User needs to be an admin")
    collection = Collection(**new_collection.model_dump())
    stmt = select(Collection).where(Collection.name == collection.name)
    results = session.exec(stmt).all()
    if results:
        logger.info(
            "A collection with name {collection_name} already exists",
            collection_name=collection.name,
        )
        raise DuplicateItemException(
            error_code=422, message="A collection with this name already exists"
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

    logger.info(
        "Collection {collection_name} created by user {user}",
        collection_name=collection.name,
        user=user.email,
    )

    return collection


def get_user_collections(
    user: User,
    session: Session,
    logger: StructuredLogger,
    page: int = 1,
    page_size: int = 10,
) -> CollectionsDto:
    user_is_admin = is_user_admin_user(user) or user.is_admin
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

    collections = []
    for collection, is_manager in query_results:
        permissions = get_collection_permissions_for_user(user, collection, session)
        if CollectionPermissionEnum.VIEW not in permissions:
            logger.error(msg="No permission to view collection")
            raise NoPermissionException(
                error_code=401, message="Failed to retrieve available collections"
            )
        collections.append(
            CollectionDto(
                id=collection.id,
                name=collection.name,
                description=collection.description,
                created_at=collection.created_at,
                permissions=permissions,
                is_manager=is_manager,
            )
        )

    total = session.exec(count_statement).one()

    return CollectionsDto(
        total=total,
        page=page,
        page_size=page_size,
        collections=collections,
        is_admin=user_is_admin,
    )


def update_collection_by_id(
    collection_id: UUID,
    collection_details: CollectionBase,
    session: Session,
    user: User,
    logger: StructuredLogger,
) -> CollectionDto:
    if collection := session.get(Collection, collection_id):
        permissions = get_collection_permissions_for_user(user, collection, session)
        if (
            CollectionPermissionEnum.EDIT not in permissions
            or CollectionPermissionEnum.VIEW not in permissions
        ):
            raise NoPermissionException(
                error_code=401, message="Permission to edit collection not found"
            )
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

        logger.info(
            "Collection {collection_name} updated by user {user}",
            collection_name=collection.name,
            user=user.email,
        )
        return CollectionDto(
            id=collection.id,
            name=collection.name,
            description=collection.description,
            created_at=collection.created_at,
            is_manager=is_manager,
        )
    else:
        logger.info("Collection {collection_id} not found", collection_id=collection_id)
        raise ItemNotFoundException("Collection not found", 403)


def delete_collection_by_id(
    user: User, collection_id: UUID, session: Session, logger: StructuredLogger
) -> UUID:
    check_user_is_member_of_collection(
        user, collection_id, session, struct_logger=logger
    )
    if collection := session.get(Collection, collection_id):
        permissions = get_collection_permissions_for_user(user, collection, session)
        if CollectionPermissionEnum.DELETE not in permissions:
            raise NoPermissionException(
                "Permission to delete collection not found", 401
            )
        objects = config.s3_client.list_objects_v2(
            Bucket=config.data_s3_bucket, Prefix=f"{config.s3_prefix}/{collection_id}"
        )
        if contents := objects.get("Contents"):
            object_keys = [{"Key": obj["Key"]} for obj in contents]
            config.s3_client.delete_objects(
                Bucket=config.data_s3_bucket, Delete={"Objects": object_keys}
            )

        session.delete(collection)
        session.commit()
        logger.info(
            "Collection {collection_id}:{collection_name} deleted",
            collection_id=collection_id,
            collection_name=collection.name,
        )
        return collection_id
    else:
        raise ItemNotFoundException(error_code=404, message="Collection not found")


def create_resource_from_file(
    user: User,
    collection_id: UUID,
    session: Session,
    logger: StructuredLogger,
    file: File,
) -> Resource:
    check_user_is_member_of_collection(
        user, collection_id, session, struct_logger=logger
    )

    if collection := session.get(Collection, collection_id):
        permissions = get_collection_permissions_for_user(user, collection, session)
        if CollectionPermissionEnum.MANAGE_RESOURCES not in permissions:
            raise NoPermissionException(
                "User does not have permission to manage resources for this collection"
            )

        resource, processing_time = __process_resource(
            resource_name=file.filename,
            collection_id=collection_id,
            content_type=file.content_type,
            content=file.file.read(),
            session=session,
            user=user,
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
            "Resource created from file upload. File name: {file_name}. File type: {file_type}. File size (bytes): {file_size}. User: {user}. Processing time (ms): {processing_time}.",
            file_name=file.filename,
            file_type=file.content_type,
            file_size=file.size,
            user=user,
            processing_time=processing_time,
        )

        return resource
    else:
        raise ItemNotFoundException(error_code=404, message="Collection not found")


async def create_resource_from_urls(
    user: User,
    session: Session,
    collection_id: UUID,
    logger: StructuredLogger,
    urls: list[str],
) -> list[Resource]:
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
            "Resource created from url scrape. URl count: {url_count}. User: {user}. Processing time (ms): {processing_time}.",
            url_count=len(urls),
            user=user,
            processing_time=(scrape_processing_time + processing_total).total_seconds()
            * 1000,
        )
        return resources
    else:
        raise ItemNotFoundException(error_code=404, message="Collection not found")


def get_documents_for_resource_by_id(user: User, collection_id: UUID, session: Session, logger: StructuredLogger, resource_id: UUID, page: int = 1, page_size: int = 10) -> Chunks:
    check_user_is_member_of_collection(
        user, collection_id, session, is_manager=False, struct_logger=logger
    )

    resource = session.get(Resource, resource_id)
    collection = session.get(Collection, collection_id)

    if not resource:
        raise ItemNotFoundException(error_code=404, message="Resource not found")

    if not collection:
        raise ItemNotFoundException(error_code=404, message="Collection not found")

    collection_permissions = get_collection_permissions_for_user(user, collection, session)
    resource_permissions = get_collection_permissions_for_user(user, resource, session)

    if CollectionPermissionEnum.VIEW not in collection_permissions or ResourcePermissionEnum.VIEW not in resource_permissions:
        raise NoPermissionException(error_code=401, message="No permission to view documents for this resource")

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
        "{total} document(s) for resource {resource_id} retrieved by user {user}",
        total=total,
        resource_id=resource_id,
        user=str(user),
    )

    return Chunks(
        collection_id=collection_id,
        resource_id=resource_id,
        page=page,
        total=total,
        page_size=page_size,
        documents=documents,
    )


def delete_resource_by_id(user: User, session: Session, collection_id: UUID, resource_id: UUID, logger: StructuredLogger) -> UUID:
    check_user_is_member_of_collection(
        user, collection_id, session, struct_logger=logger
    )

    if resource := session.get(Resource, resource_id):
        permissions = get_resource_permissions_for_user(user, resource, session)

        if ResourcePermissionEnum.DELETE not in permissions:
            raise NoPermissionException(error_code=401, message="No permission to delete documents for this resource")

        config.s3_client.delete_object(
            Bucket=config.data_s3_bucket,
            Key=f"{config.s3_prefix}/{collection_id}/{resource_id}",
        )

        session.delete(resource)
        session.commit()
        logger.info("Resource {resource_id} deleted", resource_id=resource_id)
        return resource_id
    else:
        raise ItemNotFoundException(error_code=404, message="Resource not found")

def get_resource_by_id(user: User, session: Session, collection_id: UUID, resource_id: UUID, logger: StructuredLogger) -> Resource:
    check_user_is_member_of_collection(
        user, collection_id, session, is_manager=False, struct_logger=logger
    )

    if resource := session.get(Resource, resource_id):
        permissions = get_resource_permissions_for_user(user, resource, session)
        if ResourcePermissionEnum.VIEW not in permissions:
            raise NoPermissionException(error_code=401, message="No permission to view this resource")
        logger.info("Resource {resource_id} found ", resource_id=resource_id)
        return resource
    else:
        raise ItemNotFoundException(error_code=404, message="Resource not found")

def get_collection_user_roles_by_id(user: User, session: Session, collection_id: UUID, logger: StructuredLogger, page: int = 1, page_size: int = 10) -> UserRoleList:
    check_user_is_member_of_collection(
        user, collection_id, session, struct_logger=logger
    )

    if session.get(Collection, collection_id):
        permissions = get_collection_permissions_for_user(user, collection_id, session)
        if CollectionPermissionEnum.VIEW not in permissions or CollectionPermissionEnum.MANAGE_USERS not in permissions:
            raise NoPermissionException(error_code=401, message="No permission to view this collections users")

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
        logger.info(
            "Retrieved user roles for collection {collection_id} for user {user}. {total} user(s) retrieved",
            collection_id=collection_id,
            user=str(user),
            total=total,
        )
        return UserRoleList(
            page=page, page_size=page_size, total=total, user_roles=user_roles_with_emails
        )
    else:
        raise ItemNotFoundException(error_code=404, message="Collection not found")

def create_user_role_on_collection(user: User, session: Session, user_role: UserRole, collection_id: UUID, logger: StructuredLogger) -> UserCollection:
    if collection := session.get(Collection, collection_id):
        check_user_is_member_of_collection(
            user, collection_id, session, struct_logger=logger
        )

        permissions = get_collection_permissions_for_user(user, collection, session)
        if CollectionPermissionEnum.MANAGE_USERS not in permissions:
            raise NoPermissionException(error_code=401, message="No permission to manage users")

        user_to_add = User.get_by_email(session, user_role.email)

        if not user_to_add:
            user_to_add = User(email=user_role.email)
            session.add(user_to_add)
            session.commit()
            session.refresh(user_to_add)

        if user_collection := session.get(
                UserCollection, {"collection_id": collection_id, "user_id": user_to_add.id}
        ):
            user_collection.role = user_role.role
        else:
            user_collection = UserCollection(
                collection_id=collection_id,
                user_id=user_to_add.id,
                role=user_role.role,
            )

        session.add(user_collection)
        session.commit()
        session.refresh(user_collection)
        logger.info(
            "Role {role} for user {user} created on collection {collection_id}",
            role=user_role.role,
            user=str(user_to_add),
            collection_id=collection_id,
        )
        return user_collection
    else:
        raise ItemNotFoundException(error_code=404, message="Collection not found")
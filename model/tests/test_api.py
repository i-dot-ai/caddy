import json
import os.path
import uuid
from uuid import uuid4

import pytest
from langchain_core.documents import Document
from sqlmodel import Session

from api.enums import CollectionPermissionEnum
from api.environment import config
from api.models import (
    Resource,
    User,
    UserCollectionWithEmail,
    UserRoleList,
)
from api.types import Chunks, CollectionsDto

s3_client = config.s3_client
CWD = os.path.dirname(os.path.abspath(__file__))


def delete_resource(session: Session, response_id: uuid.UUID):
    """helper method to tear down created resource"""
    resource = session.get(Resource, response_id)
    session.delete(resource)
    session.commit()


def test_upload_txt_to_file_upload_endpoint(
    client, example_collection, admin_user, database_transaction
):
    """
    Test the `upload_txt_to_opensearch` endpoint for successful requests using dependency injection.
    """

    file_name = "test.txt"
    file_data = b"Harry the hamster is a cute little hamster."

    response = client.post(
        f"/collections/{example_collection.id}/resources",
        files={"file": (file_name, file_data)},
        headers={"Authorization": admin_user.token},
    )
    assert response.status_code == 201

    response_uuid = response.json()["id"]
    # Check return type is of UUID, as we can't check for a persistent UUID value
    try:
        _ = uuid.UUID(response_uuid)
    except ValueError:
        pytest.fail(f"Response returned an invalid UUID: {response_uuid}")

    s3_object = s3_client.get_object(
        Bucket=config.data_s3_bucket,
        Key=f"{config.s3_prefix}/{example_collection.id}/{response_uuid}/{file_name}",
    )
    assert s3_object["Body"].read() == file_data

    delete_resource(database_transaction, response_uuid)


@pytest.mark.parametrize(
    ("file_data", "expected_status"),
    [
        (("test.pdf", b"\x01\x02\x03\xff"), 422),
    ],
)
def test_upload_txt_to_file_upload_endpoint_invalid_file(
    client,
    example_collection,
    file_data,
    expected_status,
    admin_user,
    database_transaction,
):
    """
    Test the `upload_txt_to_opensearch` endpoint when an invalid file is uploaded (e.g., PDF).
    """
    response = client.post(
        f"/collections/{example_collection.id}/resources",
        files={"file": file_data},
        headers={"Authorization": admin_user.token},
    )

    assert response.status_code == expected_status
    assert response.json()["detail"] == "An issue occurred processing this file"


def test_upload_pdf_to_file_upload_endpoint(
    client, example_collection, admin_user, database_transaction
):
    """test that a real pdf can be processes by the file upload endpoint"""
    with open(os.path.join(CWD, "dummy.pdf"), "rb") as file:
        response = client.post(
            f"/collections/{example_collection.id}/resources",
            files={"file": file},
            headers={"Authorization": admin_user.token},
        )

        assert response.status_code == 201
        assert response.json()["content_type"] == "application/pdf"

        assert response.json()["filename"] == response.json()["id"]
    delete_resource(database_transaction, response.json()["id"])


def test_get_resource_documents(client, collection_manager, many_documents, admin_user):
    # GIVEN 50 resources with 10 documents each, with consecutive ids
    # WHEN I query for the third resource
    resource_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
    # ...and the 3rd page of size 2 of the documents
    response = client.get(
        f"/collections/{collection_manager.collection_id}/resources/{resource_id}/documents?page_size=2&page=3",
        headers={"Authorization": admin_user.token},
    )

    assert response.status_code == 200
    actual_result = Chunks.model_validate(response.json())
    #  I EXPECT the 4th and 5th documents to be returned
    expected_result = Chunks(
        page=3,
        page_size=2,
        total=10,
        collection_id=collection_manager.collection_id,
        resource_id=resource_id,
        documents=[
            Document(
                id="00000000-0000-0000-0000-000000000024",
                metadata={
                    "filename": "filename-02",
                    "resource_id": str(resource_id),
                    "content_type": "text/plain",
                    "created_at": "2001-01-01T01:01:00",
                    "chunk_order": 4,
                },
                page_content="resource=2, document=4",
            ),
            Document(
                id="00000000-0000-0000-0000-000000000025",
                metadata={
                    "filename": "filename-02",
                    "resource_id": str(resource_id),
                    "content_type": "text/plain",
                    "created_at": "2001-01-01T01:01:00",
                    "chunk_order": 5,
                },
                page_content="resource=2, document=5",
            ),
        ],
    )
    assert actual_result == expected_result


def test_get_resource_documents_404(
    client, collection_manager, many_documents, admin_user
):
    response = client.get(
        f"/collections/{collection_manager.collection_id}/resources/{uuid.uuid4()}/documents",
        headers={"Authorization": admin_user.token},
    )

    assert response.status_code == 404
    assert response.json() == {"message": "Not found"}


def test_get_resource_documents_401(client, collection_manager, many_documents):
    response = client.get(
        f"/collections/{collection_manager.collection_id}/resources/{uuid.uuid4()}/documents",
    )

    assert response.status_code == 401


def test_delete_resource(
    client,
    collection_manager,
    example_document,
):
    document_id = example_document.resource_id
    response = client.delete(
        f"/collections/{collection_manager.collection_id}/resources/{example_document.resource_id}",
        headers={"Authorization": collection_manager.user.token},
    )

    assert response.status_code == 200
    assert response.json() == str(document_id)


def test_delete_resource_404(client, collection_manager, admin_user):
    response = client.delete(
        f"/collections/{collection_manager.collection_id}/resources/{uuid.uuid4()}",
        headers={"Authorization": admin_user.token},
    )

    assert response.status_code == 404
    assert response.json() == {"message": "Not found"}


def test_delete_resource_401(
    client,
    collection_manager,
):
    response = client.delete(
        f"/collections/{collection_manager.collection_id}/resources/{uuid.uuid4()}",
    )

    assert response.status_code == 401


def test_get_resource(client, collection_manager, example_document):
    response = client.get(
        f"/collections/{collection_manager.collection_id}/resources/{example_document.resource_id}",
        headers={"Authorization": collection_manager.user.token},
    )

    assert response.status_code == 200
    response_json = response.json()
    assert response_json["filename"] == str(example_document.resource_id)
    assert response_json["content_type"] == example_document.resource.content_type
    assert response_json["id"] == str(example_document.resource_id)


def test_get_resource_404(client, collection_manager):
    response = client.get(
        f"/collections/{collection_manager.collection_id}/resources/{uuid4()}",
        headers={"Authorization": collection_manager.user.token},
    )

    assert response.status_code == 404
    assert response.json() == {"message": "Not found"}


def test_get_resource_401(client, collection_manager):
    response = client.get(
        f"/collections/{collection_manager.collection_id}/resources/{uuid4()}",
    )

    assert response.status_code == 401


def test_get_collections(
    client,
    another_example_collection,
    collection_manager,
):
    response = client.get(
        "/collections",
        headers={"Authorization": collection_manager.user.token},
    )

    assert response.status_code == 200

    result = response.json()
    actual = CollectionsDto.model_validate(result)

    assert len(actual.collections) == 2

    collection_a = next(
        c for c in actual.collections if c.id == collection_manager.collection_id
    )
    collection_b = next(
        c for c in actual.collections if c.id == another_example_collection.id
    )
    assert (
        collection_a.is_manager
    )  # admin_user is the manger of this one via `collection_manager`
    assert not collection_b.is_manager  # but not this one


def test_anonymous__get_collections(
    client,
    example_collection,
    another_example_collection,
):
    response = client.get("/collections")
    assert response.status_code == 401


def test_get_collection_resources(
    client, collection_manager, many_documents, normal_user
):
    # GIVEN: 50 resources
    # WHEN I query the 7th page of size 3
    response = client.get(
        f"/collections/{collection_manager.collection_id}/resources?page_size=3&page=7",
        headers={"Authorization": collection_manager.user.token},
    )

    assert response.status_code == 200
    # I EXPECT: resources 18, 19 & 20
    proto = {
        "collection_id": str(collection_manager.collection_id),
        "filename": "filename-20",
        "content_type": "text/plain",
        "created_at": "2001-01-01T01:01:00",
        "is_processed": False,
        "permissions": [
            CollectionPermissionEnum.VIEW.value,
            CollectionPermissionEnum.DELETE.value,
        ],
        "process_error": None,
        "process_time": None,
        "created_by_id": str(normal_user.id),
        "url": None,
    }

    expected_result = [
        dict(
            proto,
            id="00000000-0000-0000-0000-000000000018",
            filename="00000000-0000-0000-0000-000000000018",
        ),
        dict(
            proto,
            id="00000000-0000-0000-0000-000000000019",
            filename="00000000-0000-0000-0000-000000000019",
        ),
        dict(
            proto,
            id="00000000-0000-0000-0000-000000000020",
            filename="00000000-0000-0000-0000-000000000020",
        ),
    ]
    actual_result = response.json()["resources"]
    assert actual_result == expected_result


def test_get_collection_resources_403(client, admin_user):
    response = client.get(
        f"/collections/{uuid4()}/resources",
        headers={"Authorization": admin_user.token},
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Collection not found"}


def test_get_collection_resources_401(client):
    response = client.get(
        f"/collections/{uuid4()}/resources",
    )
    assert response.status_code == 401


def test_delete_collection(client, collection_manager):
    collection_id = str(collection_manager.collection_id)
    response = client.delete(
        f"/collections/{collection_manager.collection_id}",
        headers={"Authorization": collection_manager.user.token},
    )
    assert response.status_code == 200
    assert response.json() == collection_id


def test_delete_collection_404(client, collection_manager):
    response = client.delete(
        f"/collections/{uuid4()}",
        headers={"Authorization": collection_manager.user.token},
    )
    assert response.status_code == 404
    assert response.json() == {"message": "Not found"}


def test_delete_collection_401(client):
    response = client.delete(
        f"/collections/{uuid4()}",
    )
    assert response.status_code == 401


def test_create_collection(client, admin_user):
    collection_name = "my-collection"
    response = client.post(
        "/collections",
        json={"name": collection_name, "description": "a collection"},
        headers={"Authorization": admin_user.token},
    )
    assert response.status_code == 201
    assert response.json()["name"] == collection_name

    manager_response = client.get(
        f"/collections/{response.json()["id"]}/users",
        headers={"Authorization": admin_user.token},
    )

    assert manager_response.status_code == 200
    assert manager_response.json()["user_roles"][0]["user_id"] == str(admin_user.id)


def test_create_collection_401(client):
    collection_name = "my-collection"
    response = client.post(
        "/collections",
        json={"name": collection_name, "description": "a collection"},
    )
    assert response.status_code == 401


def test_create_collection_same_name(client, collection_manager, example_collection):
    # we can now create two collections with the same name
    response = client.post(
        "/collections",
        json={"name": example_collection.name, "description": "a collection"},
        headers={"Authorization": collection_manager.user.token},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("collection_name", "error_message"),
    [
        ("my collection", "String should match pattern '^[\\w-]+$'"),
        ("AB", "String should have at least 3 characters"),
        (
            "my-far-far-far-too-long-collection-name",
            "String should have at most 36 characters",
        ),
    ],
)
def test_create_collection_invalid_name(
    client, collection_name, error_message, admin_user
):
    response = client.post(
        "/collections",
        json={"name": collection_name, "description": "a collection"},
        headers={"Authorization": admin_user.token},
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == error_message


def test_update_collection(client, example_collection, admin_user):
    response = client.put(
        f"/collections/{example_collection.id}",
        json={"name": "new-name", "description": "new-description"},
        headers={"Authorization": admin_user.token},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "new-name"
    assert response.json()["description"] == "new-description"


def test_update_collection_403(client, admin_user):
    response = client.put(
        f"/collections/{uuid4()}",
        json={"name": "new-name", "description": "new-description"},
        headers={"Authorization": admin_user.token},
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Collection not found (Error Code: 403)"}


def test_update_collection_401(client):
    response = client.put(
        f"/collections/{uuid4()}",
        json={"name": "new-name", "description": "new-description"},
    )
    assert response.status_code == 401


def test_search(client, collection_manager, example_document, another_example_document):
    response = client.post(
        "/search",
        json={
            "query": "What are my client's redundancy rights?",
            "index_name": str(collection_manager.collection.name),
        },
        headers={"Authorization": collection_manager.user.token},
    )

    assert response.status_code == 200, response.content
    assert len(response.json()) == 1

    output = Document.model_validate(response.json()[0])
    assert isinstance(output, Document)

    assert output.page_content == example_document.text
    assert output.metadata["resource_id"] == str(example_document.resource_id)


def test_get_collections_user_roles(client, collection_manager):
    response = client.get(
        f"/collections/{collection_manager.collection_id}/users",
        headers={"Authorization": collection_manager.user.token},
    )
    assert response.status_code == 200

    expected = UserRoleList(
        page=1,
        page_size=10,
        total=1,
        user_roles=[
            UserCollectionWithEmail(
                user_email=collection_manager.user.email,
                **collection_manager.model_dump(),
            )
        ],
    ).model_dump_json()

    assert response.json() == json.loads(expected)


def test_get_collections_user_roles_401(client, collection_manager):
    response = client.get(
        f"/collections/{collection_manager.collection_id}/users",
    )
    assert response.status_code == 401


def test_create_collection_user(client, admin_user, example_collection):
    payload = {"email": admin_user.email, "role": "member"}
    response = client.post(
        f"/collections/{example_collection.id}/users",
        json=payload,
        headers={"Authorization": admin_user.token},
    )
    assert response.status_code == 201


def test_create_collection_user_401(client, admin_user, example_collection):
    payload = {"email": admin_user.email, "role": "member"}
    response = client.post(
        f"/collections/{example_collection.id}/users",
        json=payload,
    )
    assert response.status_code == 401


def test_create_collection_user_update_if_already_exists(client, collection_manager):
    payload = {"email": collection_manager.user.email, "role": "manager"}
    response = client.post(
        f"/collections/{collection_manager.collection_id}/users",
        json=payload,
        headers={"Authorization": collection_manager.user.token},
    )
    assert response.status_code == 201
    assert response.json()["role"] == "manager"


def test_create_collection_user_create_new_user(client, collection_manager):
    payload = {"email": "no.one@example.com", "role": "member"}
    response = client.post(
        f"/collections/{collection_manager.collection_id}/users",
        json=payload,
        headers={"Authorization": collection_manager.user.token},
    )
    assert response.status_code == 201


def test_create_collection_user_404_collection_not_found(client, admin_user):
    payload = {"email": admin_user.email, "role": "member"}
    response = client.post(
        f"/collections/{uuid4()}/users",
        json=payload,
        headers={"Authorization": admin_user.token},
    )
    assert response.status_code == 404
    assert response.json() == {"message": "Not found"}


def test_delete_collection_user(client, collection_manager, database_transaction):
    collection_id = collection_manager.collection_id
    user_id = collection_manager.user_id
    response = client.delete(
        f"/collections/{collection_id}/users/{user_id}",
        headers={"Authorization": collection_manager.user.token},
    )
    assert response.status_code == 200
    assert response.json()

    # check user is still there
    assert database_transaction.get(User, user_id)

    # check user is still there
    assert database_transaction.get(User, user_id)


def test_delete_collection_user_404(client, admin_user):
    response = client.delete(
        f"/collections/{uuid4()}/users/{uuid4()}",
        headers={"Authorization": admin_user.token},
    )
    assert response.status_code == 404
    assert response.json() == {"message": "Not found"}


def test_delete_collection_user_401(client, admin_user):
    response = client.delete(
        f"/collections/{uuid4()}/users/{uuid4()}",
    )
    assert response.status_code == 401


def test_get_collection_admin_user_is_attached(
    client,
    another_example_collection,
    collection_manager,
):
    response = client.get(
        "/collections/",
        headers={"Authorization": collection_manager.user.token},
    )
    assert response.status_code == 200
    assert len(response.json()["collections"]) == 2


def test_get_collection_non_admin_user_is_attached_to(
    client,
    another_example_collection,
    collection_manager_non_admin,
):
    response = client.get(
        "/collections/",
        headers={"Authorization": collection_manager_non_admin.user.token},
    )
    assert response.status_code == 200
    assert len(response.json()["collections"]) == 1


def test_healthcheck(client):
    response = client.get("/healthcheck")
    assert response.json()["sha"] == "test"


def test_upload_urls_to_upload_endpoint_422(client, example_collection, admin_user):
    fake_url = "fake_url"
    response = client.post(
        f"/collections/{example_collection.id}/resources/urls",
        json=[fake_url],
        headers={"Authorization": admin_user.token},
    )
    assert response.status_code == 422
    assert response.json() == {
        "detail": f"Unsupported URL ({fake_url}) found in URL list (Error Code: 422)"
    }


def test_upload_urls_to_upload_endpoint_401(client, example_collection, admin_user):
    response = client.post(
        f"/collections/{example_collection.id}/resources/urls",
        json={
            "urls": [
                "https://www.gov.uk/find-a-job",
                "https://www.gov.uk/guidance/changes-to-govuk",
            ]
        },
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    ("url", "expected_results", "expected_status"),
    [
        (
            "https://www.gov.uk/find-a-job",
            {
                "content_type": "text/html",
                "filename": "Find a job - GOV.UK",
                "is_processed": True,
            },
            201,
        ),
        (
            "https://www.gov.uk/guidance/changes-to-govuk",
            {
                "content_type": "text/html",
                "filename": "Changes to GOV.UK - GOV.UK",
                "is_processed": True,
            },
            201,
        ),
    ],
)
def test_upload_urls_to_upload_endpoint(
    client,
    collection_manager_non_admin,
    normal_user,
    url,
    expected_results,
    expected_status,
):
    response = client.post(
        f"/collections/{collection_manager_non_admin.collection_id}/resources/urls",
        json=[
            url,
        ],
        headers={"Authorization": normal_user.token},
    )
    assert response.status_code == 201
    resources = [Resource.model_validate(resource) for resource in response.json()]
    assert len(resources) == 1
    actual_result = resources[0]
    assert actual_result.url == url
    assert actual_result.content_type == expected_results["content_type"]
    assert actual_result.filename == expected_results["filename"]
    assert actual_result.is_processed == expected_results["is_processed"]
    assert actual_result.collection_id == collection_manager_non_admin.collection_id
    assert actual_result.created_by_id == normal_user.id

import os

import pytest

from api.environment import config


@pytest.mark.parametrize(
    "filename",
    [
        "file1.txt",
        "file2.pdf",
    ],
)
def test_file_upload(
    client, tmp_path, collection_manager, example_collection, filename
):
    file_path = os.path.join(tmp_path, filename)
    with open(file_path, "w") as f:
        f.write(f"Test content for {filename}")

    with open(file_path, "rb") as f:
        response = client.post(
            f"/collections/{example_collection.id}/resources",
            headers={"Authorization": collection_manager.user.token},
            files={"file": (filename, f, "text/plain")},
        )
        assert response.status_code == 201

    response = client.get(
        f"/collections/{example_collection.id}/resources",
        headers={
            "Authorization": collection_manager.user.token,
            "content-type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1

    s3_client = config.get_file_store_client()
    s3_object = s3_client.read_object(
        key=f"{example_collection.id}/{response.json()["resources"][0]["id"]}/{response.json()["resources"][0]["filename"]}",
        as_text=True,
    )

    assert s3_object is not None


@pytest.mark.parametrize(
    "url",
    [
        "https://www.gov.uk/check-vehicle-tax",
        "https://www.gov.uk/claim-for-injury-received-while-serving",
    ],
)
def test_url_upload(client, collection_manager, example_collection, url):
    response = client.post(
        f"/collections/{example_collection.id}/resources/urls",
        headers={
            "Authorization": collection_manager.user.token,
            "content-type": "application/json",
        },
        json=[url],
    )
    assert response.status_code == 201

    response = client.get(
        f"/collections/{example_collection.id}/resources",
        headers={
            "Authorization": collection_manager.user.token,
            "content-type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1

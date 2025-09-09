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
def test_file_upload(client, tmp_path, admin_user, example_collection, filename):
    file_path = os.path.join(tmp_path, filename)
    with open(file_path, "w") as f:
        f.write(f"Test content for {filename}")

    with open(file_path, "rb") as f:
        response = client.post(
            f"/collections/{example_collection.id}/resources",
            headers={"Authorization": admin_user.token},
            files={"file": (filename, f, "text/plain")},
        )
        assert response.status_code == 201

    response = client.get(
        f"/collections/{example_collection.id}/resources",
        headers={
            "Authorization": admin_user.token,
            "accept": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1

    s3_keys = {
        item["Key"]
        for item in config.s3_client.list_objects_v2(
            Bucket=config.data_s3_bucket,
            Prefix=f"{config.s3_prefix}/{example_collection.id}",
        )["Contents"]
    }
    resource_ids = {
        f"{config.s3_prefix}/{example_collection.id}/{item['id']}/"
        for item in response.json()["resources"]
    }
    assert all(
        any(resource_id in s3_key for s3_key in s3_keys) for resource_id in resource_ids
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://www.gov.uk/check-vehicle-tax",
        "https://www.gov.uk/claim-for-injury-received-while-serving",
    ],
)
def test_url_upload(client, tmp_path, admin_user, example_collection, url):
    response = client.post(
        f"/collections/{example_collection.id}/resources/urls",
        headers={"Authorization": admin_user.token},
        json={"urls": [url]},
    )
    assert response.status_code == 201

    response = client.get(
        f"/collections/{example_collection.id}/resources",
        headers={
            "Authorization": admin_user.token,
            "accept": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1

    s3_keys = {
        item["Key"]
        for item in config.s3_client.list_objects_v2(
            Bucket=config.data_s3_bucket,
            Prefix=f"{config.s3_prefix}/{example_collection.id}",
        )["Contents"]
    }
    resource_ids = {
        f"{config.s3_prefix}/{example_collection.id}/{item['id']}/"
        for item in response.json()["resources"]
    }
    assert all(
        any(resource_id in s3_key for s3_key in s3_keys) for resource_id in resource_ids
    )

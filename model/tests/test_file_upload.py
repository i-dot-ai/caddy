import os
from unittest import mock

from api.environment import config
from api.file_upload import FileUpload


# helper for monkey-patching `requests` methods
def make_test_client_method(test_client, method_name):
    def test_client_method(path, **kwargs):
        return getattr(test_client, method_name.lower())(path, **kwargs)

    return test_client_method


def test_file_upload(client, tmp_path, admin_user):
    # Given I have files in a local dir
    filenames = ["file1.txt", "file2.pdf"]
    for filename in filenames:
        file_path = os.path.join(tmp_path, filename)
        with open(file_path, "w") as f:
            f.write(f"Test content for {filename}")

    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhbGljZUBleGFtcGxlLmNvbSIsImVtYWlsIjoiYWxpY2VAZXhhbXBsZS5jb20ifQ.mock-signature"  # pragma: allowlist secret
    with (
        # make "requests" use the TestClient
        mock.patch("requests.delete", make_test_client_method(client, "delete")),
        mock.patch("requests.post", make_test_client_method(client, "post")),
        mock.patch("requests.get", make_test_client_method(client, "get")),
        # mock the token property since requests.post is mocked
        mock.patch.object(
            type(admin_user),
            "token",
            new_callable=lambda: mock.PropertyMock(return_value=f"Bearer {token}"),
        ),
    ):
        # when I run the FileUpload against that dir
        upload = FileUpload(
            token="nonsense",
            collection_name="test_collection",
            directory=tmp_path,
            url="",  # TestClient expects paths
            jwt=admin_user.token,
        )

        collection_id = upload.run()

    # Verify expected results
    response = client.get(
        f"/collections/{collection_id}/resources",
        headers={
            "x-external-access-token": "nonsense",
            "Authorization": admin_user.token,
            "accept": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json()["total"] == len(filenames)

    s3_keys = {
        item["Key"]
        for item in config.s3_client.list_objects_v2(
            Bucket=config.data_s3_bucket, Prefix=f"{config.s3_prefix}/{collection_id}"
        )["Contents"]
    }
    resource_ids = {
        f"{config.s3_prefix}/{collection_id}/{item['id']}/"
        for item in response.json()["resources"]
    }
    assert all(
        any(resource_id in s3_key for s3_key in s3_keys) for resource_id in resource_ids
    )

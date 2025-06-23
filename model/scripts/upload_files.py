import click
import requests

from api.file_upload import FileUpload


@click.command()
@click.argument("token")
@click.option("--collection", default="grants", help="collection name")
@click.option(
    "--directory",
    default="local-caddy-data",
    help="local directory to upload files from",
)
@click.option(
    "--url",
    default="https://caddy-model-external.ai.cabinetoffice.gov.uk",
    help="url of application",
)
@click.option(
    "--batch-size",
    default=50,
    help="number of files to upload in each batch (default: 50)",
)
@click.option(
    "--delete-existing",
    default=True,
    help="delete collection if it already exists",
    type=bool,
)
@click.option(
    "--collection-description",
    default=None,
    help="description of collection",
    type=str,
)
@click.option(
    "--client-id",
    default="caddy",
    help="client id of the keycloak client to login with (usually the repo name)",
)
@click.option(
    "--client-secret",
    help="client secret of the keycloak client to login with",
    hide_input=True,
)
@click.option(
    "--username",
    help="the username of your keycloak user",
)
@click.option(
    "--password",
    help="the password of the your keycloak user",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
)
@click.option(
    "--keycloak-token-url",
    help="the url to the instance of keycloak you wish to hit, with the token path",
)
def ingest_files(
    token,
    collection,
    directory,
    url,
    delete_existing,
    batch_size,
    collection_description,
    client_id,
    client_secret,
    username,
    password,
    keycloak_token_url,
):
    token_url = keycloak_token_url
    data = {
        "grant_type": "password",
        "client_id": client_id,
        "client_secret": client_secret,
        "username": username,
        "password": password,
    }
    response = requests.post(token_url, data=data)
    jwt = response.json().get("access_token", None)
    if not jwt:
        print("No JWT received from keycloak")
        exit(1)
    process = FileUpload(
        token=token,
        collection_name=collection,
        directory=directory,
        url=url,
        delete_existing_collection=delete_existing,
        batch_size=batch_size,
        collection_description=collection_description,
        jwt=f"Bearer {jwt}",
    )
    process.run()


if __name__ == "__main__":
    ingest_files()

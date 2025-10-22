[![Tests](https://github.com/i-dot-ai/caddy-model/actions/workflows/main_tests.yaml/badge.svg?branch=main)](https://github.com/i-dot-ai/caddy-model/actions/workflows/main_tests.yaml?query=branch%3Amain)


# 🦉 Caddy Model

## Development Setup

### Setup

Install `poetry`, run `poetry lock` and configure your IDE to use the poetry interpreter.

### Running the Application

The `make run` command starts the backing services (`Qdrant`, `PostgreSQL`, `Minio`). Once these have come up,
run either `make run_backend`+`make run_frontend` or run the backend and frontend using your IDE.

```bash
make run
make run_frontend
make run_backend
```

## How to ingest data into Caddy

### PDFs/files in a local directory to a remote instance
If you have a local directory with your files, you can upload them to the Caddy resource by running the following command:
1. `poetry run python scripts/upload_files.py AUTH_TOKEN --url TARGET_URL --collection COLLECTION_NAME --directory LOCAL_DIRECTORY --client-id CLIENT_ID --client-secret CLIENT_SECRET --username USERNAME --keycloak-token-url KEYCLOAK_TOKEN_URL`
where

- `AUTH_TOKEN` is your Caddy API key
- `TARGET_URL` is the URL of the Caddy resource
- `COLLECTION_NAME` is the name of the collection in the Caddy resource
- `LOCAL_DIRECTORY` is the local directory with your files.
- `CLIENT_ID` is the id of the keycloak client
- `CLIENT_SECRET` is the secret of the above client
- `USERNAME` is your keycloak username
- `KEYCLOAK_TOKEN_URL` is the url keycloak uses to return a jwt token

You'll also need to provide your keycloak password when requested.

### PDFs/files in an S3 bucket

First download the relevant documents to a local directory, then run the upload script.
1. `aws s3 sync s3://<my-bucket>/local-caddy-data`
2. `poetry run python scripts/upload_files.py AUTH_TOKEN --url TARGET_URL --collection COLLECTION_NAME --directory LOCAL_DIRECTORY --client-id CLIENT_ID --client-secret CLIENT_SECRET --username USERNAME --keycloak-token-url KEYCLOAK_TOKEN_URL`

### JSON scraped files
If you want to scrape the data from the web, and you have used the  `caddy/scraper/run_scrape.py` script with the scrape_config.json, which scrapes data from the web and save a json file in a local directory, then you can upload the json files to the Caddy resource by running the following command:
1. `poetry run python scripts/upload_files.py AUTH_TOKEN --url TARGET_URL --collection COLLECTION_NAME --directory LOCAL_DIRECTORY --client-id CLIENT_ID --client-secret CLIENT_SECRET --username USERNAME --keycloak-token-url KEYCLOAK_TOKEN_URL`

If you have a website such as the GCOE website, which requires a login, then you can use the `caddy/scraper/run_scrape.py` script to scrape the data from the web and save a json file in a local directory. Then you can upload the json files to the Caddy resource by running the above command.

## 📂  How to use the collections

### Find existing collections
You can find all existing collections, and their metadata such as names, descriptions, ids etc using this command:
```
curl -X GET \
  -H "x-external-access-token: $AUTH_TOKEN" \
  -H "accept: application/json" \
  "${CADDY_URL:-https://caddy-model-external.ai.cabinetoffice.gov.uk}/collections" \
  | jq '.'
```

### ➕ Create a New Collection
You can create a new collection e.g. for a completely new dataset using the following command:
```
curl -X POST -H "Content-Type: application/json" -H "Authorization: Bearer AUTH_TOKEN" -d '{"name": "my-collection", "description": "a collection"}' https://caddy-model-external.ai.cabinetoffice.gov.uk/collections
```
This uses the `POST /collections` endpoint.

### ❌ Delete a Collection
To delete a collection, you can use the following command, warning once deleted you cannot recover the collection, and this will delete all the resources e.g. documents in the collection.
```
curl -X DELETE -H "Authorization: Bearer AUTH_TOKEN" https://caddy-model-external.ai.cabinetoffice.gov.uk/collections/my-collection
```
This uses the `DELETE /collections/{collection_id}` endpoint.

### 📁 Resources
### 📤 Upload a File to a Collection
If you want to upload a single file to an existing collection, e.g. your expanding the data set, you can use the following command:
```
curl -X POST -H "Content-Type: multipart/form-data" -H "Authorization: Bearer AUTH_TOKEN" -F "file=@my-file.pdf" https://caddy-model-external.ai.cabinetoffice.gov.uk/collections/my-collection/resources
```
This uses the `POST /collections/{collection_id}/resources` endpoint.

file: The file to upload

### 🗃️ List Resources in a Collection
If you want to list all the resources in a collection, e.g. to see all the underlying documents and data in the collection, to check size, format etc, you can use the following command.
```
curl -X GET -H "Authorization: Bearer AUTH_TOKEN" https://caddy-model-external.ai.cabinetoffice.gov.uk/collections/my-collection/resources
```
This uses the `GET /collections/{collection_id}/resources` endpoint.

Query Parameters:
page: Page number (default: 1)
page_size: Items per page (default: 10)

### ❌ Delete a Resource from a Collection
If you want to delete a resource from a collection, e.g. if you want to remove a file from the collection because it is no longer relevant, you can use the following command.
```
curl -X DELETE -H "Authorization: Bearer AUTH_TOKEN" https://caddy-model-external.ai.cabinetoffice.gov.uk/collections/my-collection/resources/my-resource
```
This uses the `DELETE /collections/{collection_id}/resources/{resource_id}` endpoint.

### 📄 List Documents for a Resource
If you want to list all the documents for a resource, e.g. you have multiple documents per resource such as a pdf and docx, and you want to see the underlying documents and data in the resource, you can use the following command.
```
curl -X GET -H "Authorization: Bearer AUTH_TOKEN" https://caddy-model-external.ai.cabinetoffice.gov.uk/collections/my-collection/resources/my-resource/documents
```
This uses the `GET /collections/{collection_id}/resources/{resource_id}/documents` endpoint.

Query Parameters:
page: Page number (default: 1)

### Search all the collections
If you want to search all the collections, e.g. if you needed to know the names of all the collections, you can use the following command.
```
curl -X GET -H "Authorization: Bearer AUTH_TOKEN" https://caddy-model-external.ai.cabinetoffice.gov.uk/collections
```
This uses the `GET /collections` endpoint.

# database
When changes are made to SALModels you can reflect this in Postgres by creating a migration:

```commandline
poetry run alembic revision --autogenerate -m "<your migration message>"
```

This will create a new file in `/alembic/versions`, you should commit this file as part of any code changes.

Migrations wil automatically be applied when running in docker. When running locally you can apply them by running this command:

```commandline
poetry run alembic upgrade head
```


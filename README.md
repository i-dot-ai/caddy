# 🦉 Caddy

Caddy is a Retrieval-Augmented Generation (RAG) platform combining:

- `model`: A FastAPI-based LLM service backed by OpenSearch
- `scraper`: A semi-redundant scraper for uploading large sites in batches
- `frontend`: A collection, resource and user management UI

## 📦 Components

| Folder     | Description                                 |
|------------|---------------------------------------------|
| `model`    | Qdrant integration and document ingestion   |
| `scraper`  | Scraping, summarization, doc parsing        |
| `frontend` | Resource, collection and user management UI |

## 🚀 Getting Started

With Docker:

```bash
cp .env.example .env
```

And populate the `.env` file with the necessary vars. Then run this to bring up the backing services:

```bash
make run
```

Following the backing services coming up (`qdrant`, `postgres` and `minio`), run the model and frontend
in the way that you see fit, either through your IDE of via the make commands:

```bash
make run_frontend
make run_backend
```

**Important note**: you should allocate at least 4GB for Docker or performance will be horrible and qdrant may struggle.

### Working with dependencies

If you change a dependency in `pyproject.toml` you will need to rebuild the app if you are running the app in docker.

Do this using

```
docker compose build model --no-cache
```

To drop data volumes, which you may want to do if you change the database init
script in `./model/scripts/postgres-init.sql` or some qdrant settings,
you'll need to drop the volumes. `docker volume rm` will not work for volumes
created by `docker compose`, so use the following command:

```
# drop all volumes including Qdrant, postgres etc
docker compose down --volumes
```
### 📂 Features

- Semantic and lexical document search
- Qdrant-backed vector store
- PDF/DOCX/web content ingestion
- Authenticated scraping support
- AWS/Google/Azure storage, local directory support
- FastAPI backend + Astro frontend
- Data Ingestion & Collection Management

🧪 Testing
```bash
make run_tests
```

### 🧠 Architecture

- FastAPI (REST API)
- Qdrant (vector DB)
- PostgreSQL (metadata)
- Minio/S3 (document storage)
- Astro (admin UI)

### 🧾 License
MIT

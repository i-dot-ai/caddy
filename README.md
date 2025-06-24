# 🦉 Caddy

Caddy is a Retrieval-Augmented Generation (RAG) platform combining:

- `model`: A FastAPI-based LLM service backed by OpenSearch
- `scraper`: A document scraper supporting structured ingest from websites, files, and S3

## 📦 Components

| Folder   | Description                            |
|----------|----------------------------------------|
| `model`  | LLM + OpenSearch API and ingestion     |
| `scraper`| Scraping, summarization, doc parsing   |

## 🚀 Getting Started

With Docker:

```bash
cp docker-compose-config/.env.example docker-compose-config/.env
```

And populate the `docker-compose-config/.env` file with the necessary vars. Then

```bash
docker compose up
```

If you need to work on GovAI client at the same time, you can use the
`local-client` override. When the override is active, docker compose will draw
the client from `../gov-ai-client`. To activate the override, use the `-f`
option for `docker compose`.

```bash
 docker compose -f docker-compose.yaml -f docker-compose-config/local-client.yaml up
 ```

**Important note**: you must allocate at least 4GB for Docker or performance will be horrible and opensearch will keep dying.

### Working with dependencies

If you change a dependency in `pyproject.toml` you will need to rebuild the app.

Do this using

```
docker compose build model --no-cache
```

To drop data volumes, which you may want to do if you change the database init
script in `./model/scripts/postgres-init.sql` or some OpenSearch settings,
you'll need to drop the volumes. `docker volume rm` will not work for volumes
created by `docker compose`, so use the following command:

```
# drop all volumes including OpenSearch, postgres etc
docker compose down --volumes
```
### 📂 Features

- Semantic and lexical document search
- OpenSearch-backed vector store
- PDF/DOCX/web content ingestion
- Authenticated scraping support
- S3, local directory support
- FastAPI + Streamlit frontend
- Data Ingestion & Collection Management

🧪 Testing
```bash
make run_tests
```

### 🧠 Architecture

- FastAPI (REST API)
- OpenSearch (vector DB)
- PostgreSQL (metadata)
- Streamlit (query UI)

### 🧾 License
MIT

#!/bin/sh

poetry run alembic upgrade head

poetry run python scripts/initialize_admin_users.py

poetry run uvicorn api.main:app --host 0.0.0.0 --port 8080

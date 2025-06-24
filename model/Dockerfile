FROM python:3.12-slim

WORKDIR /app

RUN apt update -y
RUN apt install curl -y # for healthcheck

# Copy application code
COPY . .

RUN pip install poetry

# poetry must use .venv
ENV POETRY_VENV_IN_PROJECT=1
RUN poetry install --no-interaction --no-root

EXPOSE 8080

ENV PYTHONPATH="${PYTHONPATH}:."

RUN chmod +x start.sh
CMD ["./start.sh"]

FROM python:3.12.5-slim

RUN pip install poetry

COPY scraper/ .

RUN poetry install --no-root

ENTRYPOINT ["poetry", "run", "python", "run_scrape.py"]
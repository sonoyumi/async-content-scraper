FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
RUN pip install .

RUN playwright install --with-deps chromium

COPY alembic.ini ./
COPY migrations ./migrations
COPY config ./config
COPY deploy ./deploy
RUN chmod +x ./deploy/healthcheck.sh

ENTRYPOINT ["scraper"]
CMD ["run"]

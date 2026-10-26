FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src \
    PIP_DISABLE_PIP_VERSION_CHECK=1 DBT_PROFILES_DIR=/app/dbt
WORKDIR /app

FROM base AS app
# Requirements first: this layer stays cached until the pins change.
COPY requirements.txt constraints.txt ./
# dbt-core's dependency dbt-core-experimental-parser downloads ~55 MB while it builds.
# A dropped connection fails the whole step, so each pip install is retried (3 attempts).
RUN for i in 1 2 3; do \
      pip install --no-cache-dir -c constraints.txt -r requirements.txt && exit 0; \
      echo "pip failed (attempt $i), retrying"; sleep 5; \
    done; exit 1
COPY . .

FROM app AS dev
RUN for i in 1 2 3; do \
      pip install --no-cache-dir -c constraints.txt -r requirements-dev.txt && exit 0; \
      echo "pip failed (attempt $i), retrying"; sleep 5; \
    done; exit 1

FROM base AS orchestrator
COPY requirements.txt requirements-orchestration.txt constraints.txt ./
RUN for i in 1 2 3; do \
      pip install --no-cache-dir -c constraints.txt -r requirements-orchestration.txt && exit 0; \
      echo "pip failed (attempt $i), retrying"; sleep 5; \
    done; exit 1
COPY . .

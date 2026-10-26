# Pinned release (not "latest"): 6.1.0, published 2026-09-07.
FROM apache/superset:6.1.0
USER root
# The metadata database and the gold layer are both PostgreSQL, so the image needs psycopg2.
# Install it only if the image does not already ship it.
RUN /app/.venv/bin/python -c "import psycopg2" 2>/dev/null \
    || uv pip install --python /app/.venv/bin/python psycopg2-binary
COPY superset_config.py /app/pythonpath/superset_config.py
USER superset

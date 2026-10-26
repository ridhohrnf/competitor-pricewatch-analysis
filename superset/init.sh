#!/bin/sh
set -eu

superset db upgrade

# create-admin fails when the user already exists, which is fine on a re-run.
superset fab create-admin \
  --username "$SUPERSET_ADMIN_USER" --firstname Admin --lastname User \
  --email admin@pricewatch.local --password "$SUPERSET_ADMIN_PASSWORD" \
  || echo "admin user already exists"

superset init

if [ -f /app/dashboards/superset/metadata.yaml ]; then
  # An export masks the connection password (XXXXXXXXXX) and an empty Superset refuses to import
  # a new connection without one. Fill it in on a temporary copy; the files in the repo stay masked.
  rm -rf /tmp/import && mkdir -p /tmp/import
  cp -r /app/dashboards/superset /tmp/import/superset
  python - <<'PY'
import os
import pathlib

for f in pathlib.Path("/tmp/import/superset/databases").glob("*.yaml"):
    f.write_text(f.read_text().replace(":XXXXXXXXXX@", ":" + os.environ["BI_READER_PASSWORD"] + "@"))
PY
  # Superset wants a zip with exactly one top-level folder.
  cd /tmp/import && python -m zipfile -c /tmp/dashboards.zip superset
  superset import-dashboards -p /tmp/dashboards.zip -u "$SUPERSET_ADMIN_USER"
else
  echo "no dashboard export in dashboards/superset/ yet: build one in the UI, then run make dashboard-export"
fi

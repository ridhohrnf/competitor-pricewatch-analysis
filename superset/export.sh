#!/bin/sh
set -eu
rm -rf /tmp/export /tmp/export.zip && mkdir /tmp/export
superset export-dashboards -f /tmp/export.zip
python -m zipfile -e /tmp/export.zip /tmp/export
rm -rf /app/dashboards/superset && mkdir -p /app/dashboards/superset
cp -r /tmp/export/*/. /app/dashboards/superset/
echo "exported to dashboards/superset/"

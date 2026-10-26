import os

# Superset refuses to start with its default key.
SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]

# Superset's own settings (users, charts, dashboards) live in the "superset" database
# created by db/init/001_schemas.sql, not in the data schemas.
SQLALCHEMY_DATABASE_URI = (
    f"postgresql+psycopg2://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
    f"@postgres:5432/superset"
)

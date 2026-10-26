"""FastAPI app: uvicorn pricewatch.api.main:app  →  OpenAPI docs at /docs."""

from fastapi import FastAPI

from pricewatch import __version__
from pricewatch.api.routers import router

app = FastAPI(
    title="pricewatch API",
    version=__version__,
    description=(
        "Competitor prices and pricing recommendations for Unilever products, served from the "
        "gold layer only (database role `api_app` cannot read raw or silver).\n\n"
        "Get a token at `POST /auth/token` (demo users: analyst / analyst123, admin / admin123), "
        "then click **Authorize**. Every price row has `data_origin`: `live` (crawled) or "
        "`sample` (synthetic)."
    ),
)
app.include_router(router)

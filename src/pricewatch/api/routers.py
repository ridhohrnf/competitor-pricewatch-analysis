from collections.abc import Callable
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.security import OAuth2PasswordRequestForm

from pricewatch.api import schemas
from pricewatch.api.auth import User, authenticate, create_token, require_role
from pricewatch.api.config import ApiSettings, get_api_settings
from pricewatch.api.deps import Paging, get_recommender, get_repository
from pricewatch.api.repository import Repository

Repo = Annotated[Repository, Depends(get_repository)]
Reader = Annotated[User, Depends(require_role("analyst", "admin"))]
Admin = Annotated[User, Depends(require_role("admin"))]
MasterKey = Annotated[str, Path(pattern=r"^[0-9a-f]{32}$", description="md5 product key")]

router = APIRouter()


@router.post("/auth/token", response_model=schemas.Token, tags=["auth"])
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    settings: Annotated[ApiSettings, Depends(get_api_settings)],
):
    user = authenticate(form.username, form.password, settings)
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="wrong username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return schemas.Token(
        access_token=create_token(user, settings),
        expires_in_minutes=settings.jwt_expire_minutes,
        role=user.role,
    )


@router.get("/health", response_model=schemas.Health, tags=["health"])
def health(settings: Annotated[ApiSettings, Depends(get_api_settings)]):
    import psycopg

    try:
        with psycopg.connect(settings.database_url, connect_timeout=3) as conn:
            platforms = Repository(conn).platform_health()
    except psycopg.Error:
        return schemas.Health(status="degraded", database="unreachable")
    ok = any(p["last_live_status"] == "success" for p in platforms)
    return schemas.Health(status="ok" if ok else "degraded", database="ok", platforms=platforms)


@router.get("/products", response_model=schemas.Page[schemas.Product], tags=["products"])
def list_products(
    _: Reader,
    repo: Repo,
    paging: Annotated[Paging, Depends()],
    brand: Annotated[str | None, Query(max_length=50)] = None,
    category: Annotated[str | None, Query(max_length=50)] = None,
    q: Annotated[
        str | None, Query(min_length=2, max_length=100, description="name contains")
    ] = None,
    data_origin: schemas.DataOrigin | None = None,
):
    rows, total = repo.list_products(brand, category, q, data_origin, paging.page, paging.page_size)
    return {"items": rows, "page": paging.page, "page_size": paging.page_size, "total": total}


@router.get(
    "/products/{product_master_key}", response_model=schemas.ProductDetail, tags=["products"]
)
def get_product(product_master_key: MasterKey, _: Reader, repo: Repo):
    product = repo.get_product(product_master_key)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="product not found")
    return product


@router.get("/prices", response_model=schemas.Page[schemas.PricePoint], tags=["prices"])
def list_prices(
    _: Reader,
    repo: Repo,
    paging: Annotated[Paging, Depends()],
    product_master_key: Annotated[str | None, Query(pattern=r"^[0-9a-f]{32}$")] = None,
    platform: schemas.Platform | None = None,
    data_origin: schemas.DataOrigin | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="date_from must be on or before date_to"
        )
    rows, total = repo.list_prices(
        product_master_key, platform, data_origin, date_from, date_to, paging.page, paging.page_size
    )
    return {"items": rows, "page": paging.page, "page_size": paging.page_size, "total": total}


@router.get(
    "/recommendations",
    response_model=schemas.Page[schemas.Recommendation],
    tags=["recommendations"],
)
def list_recommendations(
    _: Reader,
    repo: Repo,
    paging: Annotated[Paging, Depends()],
    product_master_key: Annotated[str | None, Query(pattern=r"^[0-9a-f]{32}$")] = None,
    as_of_date: date | None = None,
    run_id: Annotated[str | None, Query(pattern=r"^[0-9a-f-]{36}$")] = None,
    data_origin: schemas.DataOrigin | None = None,
):
    run_id = run_id or repo.latest_run_id()
    if run_id is None:
        return {"items": [], "page": paging.page, "page_size": paging.page_size, "total": 0}
    rows, total = repo.list_recommendations(
        product_master_key, as_of_date, run_id, data_origin, paging.page, paging.page_size
    )
    return {"items": rows, "page": paging.page, "page_size": paging.page_size, "total": total}


@router.post(
    "/recommendations/runs",
    response_model=schemas.RunResult,
    status_code=status.HTTP_201_CREATED,
    tags=["recommendations"],
)
def trigger_recommendation_run(
    _: Admin, run: Annotated[Callable[[], dict], Depends(get_recommender)]
):
    return run()

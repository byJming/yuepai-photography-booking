from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from app.api.deps import Db
from app.core.api import success
from app.services.public import PublicContentService

router = APIRouter(tags=["公开内容"])


def _service(request: Request) -> PublicContentService:
    return PublicContentService(request.app.state.settings.media_public_base_url)


@router.get("/bootstrap")
def bootstrap(request: Request, db: Db) -> dict[str, Any]:
    return success(request, _service(request).bootstrap(db))


@router.get("/portfolio-series")
def portfolio_series(
    request: Request,
    db: Db,
    category: str | None = Query(default=None, max_length=32),
    cursor: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=10, ge=1, le=20),
) -> dict[str, Any]:
    items, next_cursor = _service(request).list_portfolios(db, category, limit, cursor)
    return success(request, {"items": items, "next_cursor": next_cursor})


@router.get("/portfolio-series/{slug}")
def portfolio_detail(slug: str, request: Request, db: Db) -> dict[str, Any]:
    return success(request, _service(request).portfolio_detail(db, slug))


@router.get("/booking-options")
def booking_options(request: Request, db: Db) -> dict[str, Any]:
    return success(request, {"groups": _service(request).booking_options(db)})


@router.get("/availability")
def availability(month: str, request: Request, db: Db) -> dict[str, Any]:
    return success(request, _service(request).availability(db, month))

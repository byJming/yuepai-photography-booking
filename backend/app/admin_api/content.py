from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, UploadFile
from sqlalchemy import func, select

from app.api.deps import CsrfAdmin, CurrentAdmin, Db
from app.core.api import success
from app.core.errors import ConflictError, NotFoundError
from app.models import AuditLog, MediaAsset, PortfolioSeriesMedia
from app.schemas.admin import (
    OptionGroupRequest,
    OptionGroupUpdateRequest,
    OptionItemRequest,
    OptionItemUpdateRequest,
    PortfolioCreateRequest,
    PortfolioMediaOrderRequest,
    PortfolioUpdateRequest,
    SettingsPatchRequest,
)
from app.services.admin_content import AdminContentService
from app.services.media import MediaProcessor
from app.utils.time import utc_now

router = APIRouter(tags=["后台内容管理"])


@router.get("/portfolio-series")
def portfolios(request: Request, db: Db, admin: CurrentAdmin) -> dict[str, Any]:
    return success(request, {"items": AdminContentService().list_portfolios(db)})



@router.get("/portfolio-series/{series_id}")
def portfolio_detail(
    series_id: int, request: Request, db: Db, admin: CurrentAdmin
) -> dict[str, Any]:
    data = AdminContentService().portfolio_detail(
        db, series_id, request.app.state.settings.media_public_base_url
    )
    return success(request, data)

@router.post("/portfolio-series", status_code=201)
def create_portfolio(
    body: PortfolioCreateRequest, request: Request, db: Db, admin: CsrfAdmin
) -> dict[str, Any]:
    item = AdminContentService().create_portfolio(db, admin.id, body, request.state.request_id)
    return success(request, AdminContentService.portfolio_item(item))


@router.patch("/portfolio-series/{series_id}")
def update_portfolio(
    series_id: int,
    body: PortfolioUpdateRequest,
    request: Request,
    db: Db,
    admin: CsrfAdmin,
) -> dict[str, Any]:
    item = AdminContentService().update_portfolio(
        db, admin.id, series_id, body, request.state.request_id
    )
    return success(request, AdminContentService.portfolio_item(item))


@router.put("/portfolio-series/{series_id}/media-order")
def set_portfolio_media(
    series_id: int,
    body: PortfolioMediaOrderRequest,
    request: Request,
    db: Db,
    admin: CsrfAdmin,
) -> dict[str, Any]:
    AdminContentService().set_portfolio_media(
        db, admin.id, series_id, body, request.state.request_id
    )
    return success(request, {})


@router.post("/portfolio-series/{series_id}/publish")
def publish_portfolio(series_id: int, request: Request, db: Db, admin: CsrfAdmin) -> dict[str, Any]:
    item = AdminContentService().publish_portfolio(
        db, admin.id, series_id, request.state.request_id
    )
    return success(request, AdminContentService.portfolio_item(item))


@router.post("/portfolio-series/{series_id}/archive")
def archive_portfolio(series_id: int, request: Request, db: Db, admin: CsrfAdmin) -> dict[str, Any]:
    item = AdminContentService().archive_portfolio(
        db, admin.id, series_id, request.state.request_id
    )
    return success(request, AdminContentService.portfolio_item(item))


@router.post("/media", status_code=201)
async def upload_media(
    request: Request,
    db: Db,
    admin: CsrfAdmin,
    file: UploadFile,
    kind: str = "portfolio_image",
) -> dict[str, Any]:
    settings = request.app.state.settings
    content = await file.read(settings.media_max_upload_bytes + 1)
    processor = MediaProcessor(
        settings.media_root, settings.media_max_upload_bytes, settings.media_max_pixels
    )
    processed = processor.process(content, file.filename or "upload", kind)
    now = utc_now()
    asset = MediaAsset(
        storage_provider="local",
        object_key=processed.object_key,
        thumbnail_object_key=processed.thumbnail_object_key,
        visibility="public",
        kind=kind,
        mime_type=processed.mime_type,
        file_size=processed.file_size,
        width=processed.width,
        height=processed.height,
        sha256=processed.sha256,
        status="ready",
        created_by_admin_id=admin.id,
        created_at=now,
        updated_at=now,
    )
    db.add(asset)
    try:
        db.flush()
        db.add(
            AuditLog(
                actor_admin_user_id=admin.id,
                action="media.upload",
                entity_type="media_asset",
                entity_id=asset.id,
                request_id=request.state.request_id,
                metadata_json={"kind": kind, "file_size": processed.file_size},
                created_at=now,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        processor.delete(processed.object_key)
        processor.delete(processed.thumbnail_object_key)
        raise
    base = settings.media_public_base_url.rstrip("/")
    return success(
        request,
        {
            "id": asset.id,
            "url": f"{base}/{asset.object_key}",
            "thumbnail_url": f"{base}/{asset.thumbnail_object_key}",
            "width": asset.width,
            "height": asset.height,
            "file_size": asset.file_size,
        },
    )


@router.delete("/media/{media_id}")
def delete_media(media_id: int, request: Request, db: Db, admin: CsrfAdmin) -> dict[str, Any]:
    asset = db.get(MediaAsset, media_id)
    if asset is None or asset.status == "deleted":
        raise NotFoundError("图片不存在。")
    used = db.scalar(
        select(func.count())
        .select_from(PortfolioSeriesMedia)
        .where(PortfolioSeriesMedia.media_id == media_id)
    )
    if used:
        raise ConflictError("图片仍被作品引用，无法删除。")
    processor = MediaProcessor(
        request.app.state.settings.media_root,
        request.app.state.settings.media_max_upload_bytes,
        request.app.state.settings.media_max_pixels,
    )
    processor.delete(asset.object_key)
    processor.delete(asset.thumbnail_object_key)
    asset.status = "deleted"
    asset.updated_at = utc_now()
    db.add(
        AuditLog(
            actor_admin_user_id=admin.id,
            action="media.delete",
            entity_type="media_asset",
            entity_id=asset.id,
            request_id=request.state.request_id,
            metadata_json={},
            created_at=utc_now(),
        )
    )
    db.commit()
    return success(request, {})


@router.get("/booking-option-groups")
def options(request: Request, db: Db, admin: CurrentAdmin) -> dict[str, Any]:
    return success(request, {"groups": AdminContentService().list_options(db)})


@router.post("/booking-option-groups", status_code=201)
def create_option_group(
    body: OptionGroupRequest, request: Request, db: Db, admin: CsrfAdmin
) -> dict[str, Any]:
    item = AdminContentService().create_option_group(db, admin.id, body, request.state.request_id)
    return success(request, {"id": item.id})


@router.patch("/booking-option-groups/{group_id}")
def update_option_group(
    group_id: int,
    body: OptionGroupUpdateRequest,
    request: Request,
    db: Db,
    admin: CsrfAdmin,
) -> dict[str, Any]:
    item = AdminContentService().update_option_group(
        db, admin.id, group_id, body, request.state.request_id
    )
    return success(request, {"id": item.id})


@router.post("/booking-option-items", status_code=201)
def create_option_item(
    body: OptionItemRequest, request: Request, db: Db, admin: CsrfAdmin
) -> dict[str, Any]:
    item = AdminContentService().create_option_item(db, admin.id, body, request.state.request_id)
    return success(request, {"id": item.id})


@router.patch("/booking-option-items/{item_id}")
def update_option_item(
    item_id: int,
    body: OptionItemUpdateRequest,
    request: Request,
    db: Db,
    admin: CsrfAdmin,
) -> dict[str, Any]:
    item = AdminContentService().update_option_item(
        db, admin.id, item_id, body, request.state.request_id
    )
    return success(request, {"id": item.id})


@router.get("/settings")
def settings(request: Request, db: Db, admin: CurrentAdmin) -> dict[str, Any]:
    return success(request, AdminContentService().settings(db))


@router.patch("/settings/{key}")
def patch_setting(
    key: str,
    body: SettingsPatchRequest,
    request: Request,
    db: Db,
    admin: CsrfAdmin,
) -> dict[str, Any]:
    item = AdminContentService().patch_setting(
        db, admin.id, key, body.value, request.state.request_id
    )
    return success(request, {"key": item.setting_key, "value": item.value_json})


@router.get("/audit-logs")
def audit_logs(
    request: Request,
    db: Db,
    admin: CurrentAdmin,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    size = max(1, min(page_size, 50))
    current = max(1, page)
    total = db.scalar(select(func.count()).select_from(AuditLog)) or 0
    rows = db.scalars(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .offset((current - 1) * size)
        .limit(size)
    ).all()
    return success(
        request,
        {
            "items": [
                {
                    "id": item.id,
                    "action": item.action,
                    "entity_type": item.entity_type,
                    "entity_id": item.entity_id,
                    "request_id": item.request_id,
                    "metadata": item.metadata_json,
                    "created_at": item.created_at.isoformat() + "Z",
                }
                for item in rows
            ],
            "page": current,
            "page_size": size,
            "total": total,
        },
    )

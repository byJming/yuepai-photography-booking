from __future__ import annotations

import secrets
from typing import Any

from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.errors import DomainValidationError, NotFoundError
from app.models import (
    AppSetting,
    AuditLog,
    BookingOptionGroup,
    BookingOptionItem,
    MediaAsset,
    PortfolioSeries,
    PortfolioSeriesMedia,
)
from app.schemas.admin import (
    OptionGroupRequest,
    OptionGroupUpdateRequest,
    OptionItemRequest,
    OptionItemUpdateRequest,
    PortfolioCreateRequest,
    PortfolioMediaOrderRequest,
    PortfolioUpdateRequest,
    normalize_setting_value,
)
from app.utils.time import utc_now


class AdminContentService:
    def _audit(
        self,
        db: Session,
        admin_id: int,
        action: str,
        entity_type: str,
        entity_id: int | None,
        request_id: str,
        metadata: dict[str, Any],
    ) -> None:
        db.add(
            AuditLog(
                actor_admin_user_id=admin_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                request_id=request_id,
                metadata_json=metadata,
                created_at=utc_now(),
            )
        )

    @staticmethod
    def portfolio_item(series: PortfolioSeries) -> dict[str, Any]:
        return {
            "id": series.id,
            "slug": series.slug,
            "title": series.title,
            "subtitle": series.subtitle,
            "description": series.description,
            "category_code": series.category_code,
            "style_tags": series.style_tags_json,
            "location_text": series.location_text,
            "shot_on": series.shot_on.isoformat() if series.shot_on else None,
            "cover_media_id": series.cover_media_id,
            "status": series.status,
            "sort_order": series.sort_order,
            "published_at": series.published_at.isoformat() + "Z" if series.published_at else None,
        }

    def list_portfolios(self, db: Session) -> list[dict[str, Any]]:
        items = db.scalars(
            select(PortfolioSeries).order_by(PortfolioSeries.sort_order, PortfolioSeries.id.desc())
        ).all()
        return [self.portfolio_item(item) for item in items]

    def portfolio_detail(
        self, db: Session, series_id: int, media_base_url: str
    ) -> dict[str, Any]:
        series = self._portfolio(db, series_id)
        rows = db.execute(
            select(PortfolioSeriesMedia, MediaAsset)
            .join(MediaAsset, PortfolioSeriesMedia.media_id == MediaAsset.id)
            .where(PortfolioSeriesMedia.series_id == series.id)
            .order_by(PortfolioSeriesMedia.sort_order, PortfolioSeriesMedia.id)
        ).all()
        base = media_base_url.rstrip("/")
        return {
            **self.portfolio_item(series),
            "media": [
                {
                    "id": media.id,
                    "url": f"{base}/{media.object_key}",
                    "thumbnail_url": f"{base}/{media.thumbnail_object_key or media.object_key}",
                    "width": media.width,
                    "height": media.height,
                    "file_size": media.file_size,
                    "caption": relation.caption,
                    "status": media.status,
                }
                for relation, media in rows
            ],
        }
    def create_portfolio(
        self,
        db: Session,
        admin_id: int,
        body: PortfolioCreateRequest,
        request_id: str,
    ) -> PortfolioSeries:
        now = utc_now()
        series = PortfolioSeries(
            slug=body.slug,
            title=body.title,
            subtitle=body.subtitle,
            description=body.description,
            category_code=body.category_code,
            style_tags_json=body.style_tags,
            location_text=body.location_text,
            shot_on=body.shot_on,
            cover_media_id=body.cover_media_id,
            status="draft",
            sort_order=body.sort_order,
            created_by_admin_id=admin_id,
            created_at=now,
            updated_at=now,
        )
        db.add(series)
        db.flush()
        self._audit(
            db,
            admin_id,
            "portfolio.create",
            "portfolio_series",
            series.id,
            request_id,
            {"slug": series.slug},
        )
        db.commit()
        return series

    def _portfolio(self, db: Session, series_id: int) -> PortfolioSeries:
        series = db.get(PortfolioSeries, series_id)
        if series is None:
            raise NotFoundError("作品系列不存在。")
        return series

    def update_portfolio(
        self,
        db: Session,
        admin_id: int,
        series_id: int,
        body: PortfolioUpdateRequest,
        request_id: str,
    ) -> PortfolioSeries:
        series = self._portfolio(db, series_id)
        data = body.model_dump(exclude_unset=True)
        if "style_tags" in data:
            data["style_tags_json"] = data.pop("style_tags")
        for key, value in data.items():
            setattr(series, key, value)
        series.updated_at = utc_now()
        self._audit(
            db,
            admin_id,
            "portfolio.update",
            "portfolio_series",
            series.id,
            request_id,
            {"fields": sorted(data)},
        )
        db.commit()
        return series

    def set_portfolio_media(
        self,
        db: Session,
        admin_id: int,
        series_id: int,
        body: PortfolioMediaOrderRequest,
        request_id: str,
    ) -> None:
        series = self._portfolio(db, series_id)
        media_ids = [item.media_id for item in body.items]
        ready_count = db.scalar(
            select(func.count())
            .select_from(MediaAsset)
            .where(MediaAsset.id.in_(media_ids), MediaAsset.status == "ready")
        )
        if ready_count != len(media_ids):
            raise DomainValidationError("包含不存在或未就绪的图片。")
        db.execute(delete(PortfolioSeriesMedia).where(PortfolioSeriesMedia.series_id == series.id))
        now = utc_now()
        for index, item in enumerate(body.items):
            db.add(
                PortfolioSeriesMedia(
                    series_id=series.id,
                    media_id=item.media_id,
                    caption=item.caption,
                    sort_order=index,
                    created_at=now,
                )
            )
        if not media_ids:
            series.cover_media_id = None
        elif series.cover_media_id not in media_ids:
            series.cover_media_id = media_ids[0]
        series.updated_at = now
        self._audit(
            db,
            admin_id,
            "portfolio.media_order",
            "portfolio_series",
            series.id,
            request_id,
            {"media_count": len(media_ids)},
        )
        db.commit()

    def publish_portfolio(
        self, db: Session, admin_id: int, series_id: int, request_id: str
    ) -> PortfolioSeries:
        series = self._portfolio(db, series_id)
        media_count = (
            db.scalar(
                select(func.count())
                .select_from(PortfolioSeriesMedia)
                .where(PortfolioSeriesMedia.series_id == series.id)
            )
            or 0
        )
        incomplete = (
            not series.title
            or not series.category_code
            or not series.cover_media_id
            or media_count < 1
        )
        if incomplete:
            raise DomainValidationError("发布前必须填写标题、分类、封面并添加至少一张图片。")
        ready = db.scalar(
            select(MediaAsset.id).where(
                MediaAsset.id == series.cover_media_id, MediaAsset.status == "ready"
            )
        )
        if ready is None:
            raise DomainValidationError("封面图片尚未就绪。")
        now = utc_now()
        series.status = "published"
        series.published_at = now
        series.updated_at = now
        self._audit(
            db,
            admin_id,
            "portfolio.publish",
            "portfolio_series",
            series.id,
            request_id,
            {"slug": series.slug},
        )
        db.commit()
        return series

    def archive_portfolio(
        self, db: Session, admin_id: int, series_id: int, request_id: str
    ) -> PortfolioSeries:
        series = self._portfolio(db, series_id)
        series.status = "archived"
        series.updated_at = utc_now()
        self._audit(
            db,
            admin_id,
            "portfolio.archive",
            "portfolio_series",
            series.id,
            request_id,
            {"slug": series.slug},
        )
        db.commit()
        return series

    def list_options(self, db: Session) -> list[dict[str, Any]]:
        groups = db.scalars(
            select(BookingOptionGroup).order_by(BookingOptionGroup.sort_order)
        ).all()
        result = []
        for group in groups:
            items = db.scalars(
                select(BookingOptionItem)
                .where(BookingOptionItem.group_id == group.id)
                .order_by(BookingOptionItem.sort_order)
            ).all()
            result.append(
                {
                    "id": group.id,
                    "code": group.code,
                    "name": group.name,
                    "selection_mode": group.selection_mode,
                    "is_required": group.is_required,
                    "min_select": group.min_select,
                    "max_select": group.max_select,
                    "status": group.status,
                    "sort_order": group.sort_order,
                    "items": [
                        {
                            "id": item.id,
                            "code": item.code,
                            "name": item.name,
                            "description": item.description,
                            "reference_media_id": item.reference_media_id,
                            "metadata": item.metadata_json,
                            "status": item.status,
                            "sort_order": item.sort_order,
                        }
                        for item in items
                    ],
                }
            )
        return result

    def create_option_group(
        self, db: Session, admin_id: int, body: OptionGroupRequest, request_id: str
    ) -> BookingOptionGroup:
        now = utc_now()
        group = BookingOptionGroup(**body.model_dump(), created_at=now, updated_at=now)
        db.add(group)
        db.flush()
        self._audit(db, admin_id, "option_group.create", "option_group", group.id, request_id, {})
        db.commit()
        return group

    def update_option_group(
        self,
        db: Session,
        admin_id: int,
        group_id: int,
        body: OptionGroupUpdateRequest,
        request_id: str,
    ) -> BookingOptionGroup:
        group = db.get(BookingOptionGroup, group_id)
        if group is None:
            raise NotFoundError("选项组不存在。")
        data = body.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(group, key, value)
        if group.min_select > group.max_select or (
            group.selection_mode == "single" and group.max_select != 1
        ):
            raise DomainValidationError("选项组数量规则无效。")
        group.updated_at = utc_now()
        self._audit(db, admin_id, "option_group.update", "option_group", group.id, request_id, {})
        db.commit()
        return group

    def create_option_item(
        self, db: Session, admin_id: int, body: OptionItemRequest, request_id: str
    ) -> BookingOptionItem:
        if db.get(BookingOptionGroup, body.group_id) is None:
            raise NotFoundError("选项组不存在。")
        now = utc_now()
        data = body.model_dump()
        data["code"] = data["code"] or f"option_{secrets.token_hex(10)}"
        data["metadata_json"] = data.pop("metadata")
        item = BookingOptionItem(**data, created_at=now, updated_at=now)
        db.add(item)
        db.flush()
        self._audit(db, admin_id, "option_item.create", "option_item", item.id, request_id, {})
        db.commit()
        return item

    def update_option_item(
        self,
        db: Session,
        admin_id: int,
        item_id: int,
        body: OptionItemUpdateRequest,
        request_id: str,
    ) -> BookingOptionItem:
        item = db.get(BookingOptionItem, item_id)
        if item is None:
            raise NotFoundError("选项不存在。")
        data = body.model_dump(exclude_unset=True)
        if "metadata" in data:
            data["metadata_json"] = data.pop("metadata")
        for key, value in data.items():
            setattr(item, key, value)
        item.updated_at = utc_now()
        self._audit(db, admin_id, "option_item.update", "option_item", item.id, request_id, {})
        db.commit()
        return item

    def settings(self, db: Session) -> dict[str, Any]:
        return {
            item.setting_key: item.value_json
            for item in db.scalars(select(AppSetting).order_by(AppSetting.setting_key)).all()
        }

    def patch_setting(
        self,
        db: Session,
        admin_id: int,
        key: str,
        value: dict[str, Any],
        request_id: str,
    ) -> AppSetting:
        try:
            normalized_value = normalize_setting_value(key, value)
        except KeyError as exc:
            raise NotFoundError("设置项不存在。") from exc
        except ValidationError as exc:
            raise DomainValidationError("设置内容不完整或格式无效。") from exc
        setting = db.get(AppSetting, key)
        now = utc_now()
        if setting is None:
            setting = AppSetting(
                setting_key=key,
                value_json=normalized_value,
                is_public=key != "booking_rules",
                updated_by_admin_id=admin_id,
                updated_at=now,
            )
            db.add(setting)
        else:
            setting.value_json = normalized_value
            setting.updated_by_admin_id = admin_id
            setting.updated_at = now
        self._audit(db, admin_id, "settings.update", "app_setting", None, request_id, {"key": key})
        db.commit()
        return setting

from __future__ import annotations

import calendar
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.errors import DomainValidationError, NotFoundError
from app.models import (
    AppSetting,
    AvailabilitySlot,
    BookingOptionGroup,
    BookingOptionItem,
    MediaAsset,
    PortfolioSeries,
    PortfolioSeriesMedia,
)
from app.utils.time import SHANGHAI, as_shanghai, local_today, period_code, utc_now


class PublicContentService:
    def __init__(self, media_base_url: str) -> None:
        self._media_base_url = media_base_url.rstrip("/")

    def _url(self, object_key: str | None) -> str | None:
        return f"{self._media_base_url}/{object_key}" if object_key else None

    @staticmethod
    def _booking_horizon_months(db: Session) -> int:
        setting = db.get(AppSetting, "booking_rules")
        value = setting.value_json.get("open_months", 12) if setting else 12
        try:
            return max(1, min(int(value), 12))
        except (TypeError, ValueError):
            return 12

    @staticmethod
    def _shift_month(month: date, offset: int) -> date:
        month_index = month.year * 12 + month.month - 1 + offset
        year, month_zero = divmod(month_index, 12)
        return date(year, month_zero + 1, 1)

    def _availability_status(self, db: Session, horizon_months: int) -> dict[str, Any]:
        current_month = local_today().replace(day=1)
        month_after_horizon = self._shift_month(current_month, horizon_months)
        horizon_end = datetime(
            month_after_horizon.year,
            month_after_horizon.month,
            1,
            tzinfo=SHANGHAI,
        ).astimezone(UTC).replace(tzinfo=None)
        next_start = db.scalar(
            select(AvailabilitySlot.start_at)
            .where(
                AvailabilitySlot.status == "open",
                AvailabilitySlot.start_at >= utc_now(),
                AvailabilitySlot.start_at < horizon_end,
            )
            .order_by(AvailabilitySlot.start_at)
            .limit(1)
        )
        if next_start is None:
            return {"available": False, "text": "暂无开放档期", "next_date": None}
        next_date = as_shanghai(next_start).date()
        return {
            "available": True,
            "text": f"{next_date.month}月{next_date.day}日可约",
            "next_date": next_date.isoformat(),
        }

    def bootstrap(self, db: Session) -> dict[str, Any]:
        settings = db.scalars(select(AppSetting).where(AppSetting.is_public.is_(True))).all()
        values = {item.setting_key: item.value_json for item in settings}
        horizon_months = self._booking_horizon_months(db)
        return {
            "brand": values.get(
                "brand",
                {
                    "name": "摄影预约",
                    "eyebrow": "自然人像 · 城市记录",
                    "monthly_title": "记录平常而珍贵的瞬间",
                    "monthly_subtitle": "最终品牌名可在管理后台修改。",
                    "availability_text": "近期可约",
                    "service_area": "请与摄影师确认",
                },
            ),
            "feature_flags": values.get(
                "feature_flags", {"subscription_message": False, "reference_upload": False}
            ),
            "policy_versions": values.get(
                "policy_versions", {"privacy": "v1", "service_terms": "v1"}
            ),
            "policy_content": values.get(
                "policy_content",
                {
                    "service_scope": "单摄影师个人摄影服务。",
                    "schedule_and_pricing": "档期和费用由摄影师沟通确认。",
                    "safety_and_reschedule": "首次合作优先选择公共场所。",
                    "privacy_and_display": "预约信息只用于沟通，作品展示另行授权。",
                    "cancellation_rules": "未确认预约可由客户取消。",
                },
            ),
            "availability_status": self._availability_status(db, horizon_months),
            "booking_horizon_months": horizon_months,
        }

    def list_portfolios(
        self,
        db: Session,
        category: str | None,
        limit: int,
        cursor: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        statement = (
            select(PortfolioSeries, MediaAsset)
            .join(MediaAsset, PortfolioSeries.cover_media_id == MediaAsset.id)
            .where(PortfolioSeries.status == "published", MediaAsset.status == "ready")
        )
        if category:
            statement = statement.where(PortfolioSeries.category_code == category)
        if cursor:
            try:
                sort_order_text, series_id_text = cursor.split(":", 1)
                cursor_sort_order = int(sort_order_text)
                cursor_series_id = int(series_id_text)
                if not -10000 <= cursor_sort_order <= 10000 or cursor_series_id < 1:
                    raise ValueError
            except (TypeError, ValueError) as exc:
                raise DomainValidationError("作品分页游标无效。") from exc
            statement = statement.where(
                or_(
                    PortfolioSeries.sort_order > cursor_sort_order,
                    and_(
                        PortfolioSeries.sort_order == cursor_sort_order,
                        PortfolioSeries.id < cursor_series_id,
                    ),
                )
            )
        rows = db.execute(
            statement.order_by(PortfolioSeries.sort_order, PortfolioSeries.id.desc()).limit(
                limit + 1
            )
        ).all()
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        items = [
            {
                "id": series.id,
                "slug": series.slug,
                "title": series.title,
                "subtitle": series.subtitle,
                "category_code": series.category_code,
                "style_tags": series.style_tags_json,
                "location": series.location_text,
                "shot_on": series.shot_on.isoformat() if series.shot_on else None,
                "cover": {
                    "url": self._url(media.object_key),
                    "thumbnail_url": self._url(media.thumbnail_object_key or media.object_key),
                    "width": media.width,
                    "height": media.height,
                },
            }
            for series, media in page_rows
        ]
        next_cursor = None
        if has_more and page_rows:
            last_series = page_rows[-1][0]
            next_cursor = f"{last_series.sort_order}:{last_series.id}"
        return items, next_cursor

    def portfolio_detail(self, db: Session, slug: str) -> dict[str, Any]:
        series = db.scalar(
            select(PortfolioSeries).where(
                PortfolioSeries.slug == slug, PortfolioSeries.status == "published"
            )
        )
        if series is None:
            raise NotFoundError("作品系列不存在。")
        rows = db.execute(
            select(PortfolioSeriesMedia, MediaAsset)
            .join(MediaAsset, PortfolioSeriesMedia.media_id == MediaAsset.id)
            .where(
                PortfolioSeriesMedia.series_id == series.id,
                MediaAsset.status == "ready",
            )
            .order_by(PortfolioSeriesMedia.sort_order)
        ).all()
        return {
            "id": series.id,
            "slug": series.slug,
            "title": series.title,
            "subtitle": series.subtitle,
            "description": series.description,
            "category_code": series.category_code,
            "style_tags": series.style_tags_json,
            "location": series.location_text,
            "shot_on": series.shot_on.isoformat() if series.shot_on else None,
            "images": [
                {
                    "id": media.id,
                    "url": self._url(media.object_key),
                    "thumbnail_url": self._url(media.thumbnail_object_key or media.object_key),
                    "width": media.width,
                    "height": media.height,
                    "caption": relation.caption,
                }
                for relation, media in rows
            ],
        }

    def booking_options(self, db: Session) -> list[dict[str, Any]]:
        groups = db.scalars(
            select(BookingOptionGroup)
            .where(BookingOptionGroup.status == "active")
            .order_by(BookingOptionGroup.sort_order)
        ).all()
        result: list[dict[str, Any]] = []
        for group in groups:
            rows = db.execute(
                select(BookingOptionItem, MediaAsset)
                .outerjoin(MediaAsset, BookingOptionItem.reference_media_id == MediaAsset.id)
                .where(
                    BookingOptionItem.group_id == group.id,
                    BookingOptionItem.status == "active",
                )
                .order_by(BookingOptionItem.sort_order)
            ).all()
            result.append(
                {
                    "code": group.code,
                    "name": group.name,
                    "selection_mode": group.selection_mode,
                    "is_required": group.is_required,
                    "min_select": group.min_select,
                    "max_select": group.max_select,
                    "items": [
                        {
                            "code": item.code,
                            "name": item.name,
                            "description": item.description,
                            "metadata": item.metadata_json,
                            "reference": (
                                {
                                    "url": self._url(media.object_key),
                                    "width": media.width,
                                    "height": media.height,
                                }
                                if media is not None and media.status == "ready"
                                else None
                            ),
                        }
                        for item, media in rows
                    ],
                }
            )
        return result

    def availability(self, db: Session, month: str) -> dict[str, Any]:
        try:
            year, month_number = (int(part) for part in month.split("-"))
            first = date(year, month_number, 1)
        except (TypeError, ValueError) as exc:
            raise DomainValidationError("月份格式无效。") from exc
        current = local_today().replace(day=1)
        horizon_months = self._booking_horizon_months(db)
        max_month = self._shift_month(current, horizon_months - 1)
        if first < current or first > max_month:
            raise DomainValidationError(f"只能查询当前月到未来 {horizon_months} 个月。")
        last_day = calendar.monthrange(year, month_number)[1]
        local_start = datetime(year, month_number, 1, tzinfo=SHANGHAI)
        local_end = datetime(year, month_number, last_day, 23, 59, 59, 999999, tzinfo=SHANGHAI)
        start_utc = max(local_start.astimezone(UTC).replace(tzinfo=None), utc_now())
        end_utc = local_end.astimezone(UTC).replace(tzinfo=None)
        slots = db.scalars(
            select(AvailabilitySlot)
            .where(
                AvailabilitySlot.start_at >= start_utc,
                AvailabilitySlot.start_at <= end_utc,
            )
            .order_by(AvailabilitySlot.start_at)
        ).all()
        grouped: dict[str, list[dict[str, Any]]] = {}
        for slot in slots:
            local = as_shanghai(slot.start_at)
            grouped.setdefault(local.date().isoformat(), []).append(
                {
                    "slot_id": slot.id,
                    "code": period_code(slot.start_at),
                    "label": {"morning": "上午", "afternoon": "下午", "sunset": "傍晚"}[
                        period_code(slot.start_at)
                    ],
                    "start_at": local.isoformat(),
                    "end_at": as_shanghai(slot.end_at).isoformat(),
                    "available": slot.status == "open",
                    "public_note": slot.public_note,
                }
            )
        return {
            "month": month,
            "dates": [{"date": day, "periods": periods} for day, periods in grouped.items()],
        }

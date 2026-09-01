from __future__ import annotations

import calendar
import secrets
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.core.security import FieldCipher
from app.models import (
    AppSetting,
    AuditLog,
    Booking,
    BookingEvent,
    DataDeletionRequest,
    User,
)
from app.utils.time import utc_now

ACTIVE_BOOKING_STATUSES = {
    "submitted",
    "needs_info",
    "reschedule_proposed",
    "confirmed",
}
CANCELLED_BOOKING_STATUSES = {
    "declined",
    "cancelled_by_user",
    "cancelled_by_admin",
}


def _months_before(value: datetime, months: int) -> datetime:
    month_index = value.year * 12 + value.month - 1 - months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _retention_months(rules: dict[str, Any], key: str, default: int) -> int:
    try:
        return max(1, min(120, int(rules.get(key, default))))
    except (TypeError, ValueError):
        return default


class DataRetentionService:
    """执行可审计、不可逆的预约敏感字段清理与用户匿名化。"""

    def __init__(self, cipher: FieldCipher) -> None:
        self._cipher = cipher

    def _clear_booking(self, db: Session, booking: Booking, now: datetime) -> bool:
        if booking.sensitive_data_cleared_at is not None:
            return False
        aad = f"bookings:{booking.booking_no}"
        booking.contact_name_ciphertext = self._cipher.encrypt("已清理", f"{aad}:contact_name")
        booking.contact_phone_ciphertext = self._cipher.encrypt("", f"{aad}:contact_phone")
        booking.contact_phone_last4 = "0000"
        booking.custom_location_ciphertext = None
        booking.remark_ciphertext = None
        booking.sensitive_data_cleared_at = now
        events = db.scalars(
            select(BookingEvent).where(BookingEvent.booking_id == booking.id)
        ).all()
        for event in events:
            event.public_message = None
            event.internal_note_ciphertext = None
            event.metadata_json = {}
        return True

    def run_policy_cleanup(
        self, db: Session, *, now: datetime | None = None
    ) -> dict[str, int]:
        current = now or utc_now()
        setting = db.get(AppSetting, "booking_rules")
        rules = (
            setting.value_json
            if setting is not None and isinstance(setting.value_json, dict)
            else {}
        )
        completed_cutoff = _months_before(
            current,
            _retention_months(rules, "data_retention_completed_months", 12),
        )
        cancelled_cutoff = _months_before(
            current,
            _retention_months(rules, "data_retention_cancelled_months", 6),
        )
        bookings = db.scalars(
            select(Booking).where(
                Booking.sensitive_data_cleared_at.is_(None),
                or_(
                    (Booking.status == "completed")
                    & (func.coalesce(Booking.completed_at, Booking.updated_at) <= completed_cutoff),
                    (Booking.status.in_(CANCELLED_BOOKING_STATUSES))
                    & (func.coalesce(Booking.cancelled_at, Booking.updated_at) <= cancelled_cutoff),
                ),
            )
        ).all()
        changed = sum(1 for booking in bookings if self._clear_booking(db, booking, current))
        db.commit()
        return {"bookings_anonymized": changed}

    def list_deletion_requests(
        self,
        db: Session,
        *,
        status: str | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        statement = select(DataDeletionRequest)
        count_statement = select(func.count()).select_from(DataDeletionRequest)
        if status:
            statement = statement.where(DataDeletionRequest.status == status)
            count_statement = count_statement.where(DataDeletionRequest.status == status)
        total = db.scalar(count_statement) or 0
        rows = db.scalars(
            statement.order_by(DataDeletionRequest.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        items = []
        for item in rows:
            active_count = (
                db.scalar(
                    select(func.count())
                    .select_from(Booking)
                    .where(
                        Booking.user_id == item.user_id,
                        Booking.status.in_(ACTIVE_BOOKING_STATUSES),
                    )
                )
                or 0
            )
            items.append(
                {
                    "id": item.id,
                    "user_id": item.user_id,
                    "status": item.status,
                    "active_booking_count": active_count,
                    "created_at": item.created_at.isoformat() + "Z",
                    "processed_at": (
                        item.processed_at.isoformat() + "Z" if item.processed_at else None
                    ),
                }
            )
        return {"items": items, "page": page, "page_size": page_size, "total": total}

    def _pending_request(self, db: Session, request_id: int) -> DataDeletionRequest:
        deletion = db.get(DataDeletionRequest, request_id)
        if deletion is None:
            not_found_error = NotFoundError("数据删除申请不存在。")
            not_found_error.code = "DATA_DELETION_REQUEST_NOT_FOUND"
            raise not_found_error
        if deletion.status != "pending":
            conflict_error = ConflictError("该数据删除申请已经处理。")
            conflict_error.code = "DATA_DELETION_REQUEST_PROCESSED"
            raise conflict_error
        return deletion

    def complete_deletion_request(
        self,
        db: Session,
        deletion_request_id: int,
        admin_id: int,
        audit_request_id: str,
        *,
        now: datetime | None = None,
    ) -> DataDeletionRequest:
        current = now or utc_now()
        deletion = self._pending_request(db, deletion_request_id)
        active_count = (
            db.scalar(
                select(func.count())
                .select_from(Booking)
                .where(
                    Booking.user_id == deletion.user_id,
                    Booking.status.in_(ACTIVE_BOOKING_STATUSES),
                )
            )
            or 0
        )
        if active_count:
            error = ConflictError("该用户仍有未完成预约，请先完成或取消相关流程。")
            error.code = "DATA_DELETION_ACTIVE_BOOKINGS"
            raise error
        user = db.get(User, deletion.user_id)
        if user is None:
            raise NotFoundError("用户不存在。")
        bookings = db.scalars(select(Booking).where(Booking.user_id == user.id)).all()
        changed = sum(1 for booking in bookings if self._clear_booking(db, booking, current))
        user.openid_ciphertext = None
        user.openid_hash = secrets.token_bytes(32)
        user.status = "anonymized"
        user.last_login_at = None
        user.updated_at = current
        deletion.status = "completed"
        deletion.processed_by_admin_id = admin_id
        deletion.processed_at = current
        deletion.updated_at = current
        db.add(
            AuditLog(
                actor_admin_user_id=admin_id,
                action="data_deletion.complete",
                entity_type="data_deletion_request",
                entity_id=deletion.id,
                request_id=audit_request_id,
                metadata_json={"bookings_anonymized": changed},
                created_at=current,
            )
        )
        db.commit()
        return deletion

    def reject_deletion_request(
        self,
        db: Session,
        deletion_request_id: int,
        admin_id: int,
        audit_request_id: str,
    ) -> DataDeletionRequest:
        deletion = self._pending_request(db, deletion_request_id)
        now = utc_now()
        deletion.status = "rejected"
        deletion.processed_by_admin_id = admin_id
        deletion.processed_at = now
        deletion.updated_at = now
        db.add(
            AuditLog(
                actor_admin_user_id=admin_id,
                action="data_deletion.reject",
                entity_type="data_deletion_request",
                entity_id=deletion.id,
                request_id=audit_request_id,
                metadata_json={},
                created_at=now,
            )
        )
        db.commit()
        return deletion

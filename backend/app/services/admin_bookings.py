from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.security import FieldCipher
from app.models import AuditLog, Booking, BookingEvent, BookingOptionSelection, PortfolioSeries
from app.services.booking_views import STATUS_TEXT, BookingViewService
from app.utils.time import local_today, utc_now


class AdminBookingService:
    def __init__(self, cipher: FieldCipher) -> None:
        self._cipher = cipher
        self._views = BookingViewService(cipher)

    def dashboard(self, db: Session) -> dict[str, Any]:
        today = local_today()
        pending = (
            db.scalar(
                select(func.count()).select_from(Booking).where(Booking.status == "submitted")
            )
            or 0
        )
        needs_info = (
            db.scalar(
                select(func.count()).select_from(Booking).where(Booking.status == "needs_info")
            )
            or 0
        )
        today_confirmed = (
            db.scalar(
                select(func.count())
                .select_from(Booking)
                .where(Booking.status == "confirmed", Booking.requested_date == today)
            )
            or 0
        )
        draft_portfolios = (
            db.scalar(
                select(func.count())
                .select_from(PortfolioSeries)
                .where(PortfolioSeries.status == "draft")
            )
            or 0
        )
        upcoming = db.scalars(
            select(Booking)
            .where(
                Booking.status == "confirmed",
                Booking.requested_date >= today,
                Booking.requested_date <= today + timedelta(days=7),
            )
            .order_by(Booking.requested_date)
            .limit(20)
        ).all()
        recent = db.scalars(select(Booking).order_by(Booking.created_at.desc()).limit(5)).all()
        return {
            "pending_count": pending,
            "needs_info_count": needs_info,
            "today_confirmed_count": today_confirmed,
            "draft_portfolio_count": draft_portfolios,
            "upcoming": [self._list_item(db, item) for item in upcoming],
            "recent": [self._list_item(db, item) for item in recent],
        }

    def _list_item(self, db: Session, booking: Booking) -> dict[str, Any]:
        aad = f"bookings:{booking.booking_no}"
        cleared = booking.sensitive_data_cleared_at is not None
        name = (
            "已清理"
            if cleared
            else self._cipher.decrypt(booking.contact_name_ciphertext, f"{aad}:contact_name")
        )
        selections = db.scalars(
            select(BookingOptionSelection).where(
                BookingOptionSelection.booking_id == booking.id,
                BookingOptionSelection.group_code_snapshot == "shoot_type",
            )
        ).all()
        return {
            "booking_no": booking.booking_no,
            "status": booking.status,
            "status_text": STATUS_TEXT.get(booking.status, booking.status),
            "requested_date": booking.requested_date.isoformat(),
            "requested_period_code": booking.requested_period_code,
            "contact_name": name,
            "phone_masked": "已清理" if cleared else f"***{booking.contact_phone_last4}",
            "shoot_type": selections[0].item_name_snapshot if selections else None,
            "submitted_at": booking.submitted_at.isoformat() + "Z",
            "updated_at": booking.updated_at.isoformat() + "Z",
            "version": booking.version,
        }

    def list_bookings(
        self,
        db: Session,
        *,
        status: str | None,
        date_from: Any,
        date_to: Any,
        phone_last4: str | None,
        booking_no: str | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        statement = select(Booking)
        count_statement = select(func.count()).select_from(Booking)
        filters = []
        if status:
            filters.append(Booking.status == status)
        if date_from:
            filters.append(Booking.requested_date >= date_from)
        if date_to:
            filters.append(Booking.requested_date <= date_to)
        if phone_last4:
            filters.append(Booking.contact_phone_last4 == phone_last4)
        if booking_no:
            filters.append(Booking.booking_no == booking_no)
        if filters:
            statement = statement.where(*filters)
            count_statement = count_statement.where(*filters)
        total = db.scalar(count_statement) or 0
        items = db.scalars(
            statement.order_by(Booking.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return {
            "items": [self._list_item(db, item) for item in items],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    def detail(
        self,
        db: Session,
        admin_id: int,
        booking_no: str,
        request_id: str,
    ) -> dict[str, Any]:
        booking = db.scalar(select(Booking).where(Booking.booking_no == booking_no))
        if booking is None:
            raise NotFoundError("预约不存在。")
        detail = self._views.customer_detail(db, booking)
        aad = f"bookings:{booking.booking_no}"
        detail["contact"]["phone"] = (
            "已清理"
            if booking.sensitive_data_cleared_at is not None
            else self._cipher.decrypt(booking.contact_phone_ciphertext, f"{aad}:contact_phone")
        )
        events = db.scalars(
            select(BookingEvent)
            .where(BookingEvent.booking_id == booking.id)
            .order_by(BookingEvent.created_at)
        ).all()
        detail["internal_events"] = []
        for event in events:
            if event.actor_type != "admin":
                continue
            note = ""
            aad_value = event.metadata_json.get("internal_aad") if event.metadata_json else None
            if event.internal_note_ciphertext and aad_value:
                note = self._cipher.decrypt(event.internal_note_ciphertext, str(aad_value))
            detail["internal_events"].append(
                {
                    "event_type": event.event_type,
                    "internal_note": note,
                    "created_at": event.created_at.isoformat() + "Z",
                }
            )
        db.add(
            AuditLog(
                actor_admin_user_id=admin_id,
                action="booking.view_sensitive",
                entity_type="booking",
                entity_id=booking.id,
                request_id=request_id,
                metadata_json={"booking_no": booking.booking_no},
                created_at=utc_now(),
            )
        )
        db.commit()
        return detail

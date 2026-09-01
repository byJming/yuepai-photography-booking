from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import FieldCipher
from app.models import AvailabilitySlot, Booking, BookingEvent, BookingOptionSelection
from app.utils.time import as_shanghai

STATUS_TEXT = {
    "submitted": "已提交，待确认",
    "needs_info": "待补充信息",
    "reschedule_proposed": "摄影师建议改期",
    "confirmed": "已确认",
    "declined": "暂时无法接单",
    "cancelled_by_user": "已取消",
    "cancelled_by_admin": "已取消",
    "completed": "已完成",
}

STATUS_NOTE = {
    "submitted": "摄影师会尽快与你确认档期与费用。",
    "needs_info": "请根据摄影师说明补充预约信息。",
    "reschedule_proposed": "请查看摄影师建议并更新意向时间。",
    "confirmed": "档期已经确认，请按约定做好拍摄准备。",
    "declined": "本次暂时无法安排，感谢你的理解。",
    "cancelled_by_user": "该预约已由你取消。",
    "cancelled_by_admin": "该预约已取消，如有疑问请联系摄影师。",
    "completed": "拍摄已经完成，感谢你的信任。",
}


class BookingViewService:
    def __init__(self, cipher: FieldCipher) -> None:
        self._cipher = cipher

    def _selections(self, db: Session, booking_id: int) -> dict[str, list[dict[str, str]]]:
        rows = db.scalars(
            select(BookingOptionSelection)
            .where(BookingOptionSelection.booking_id == booking_id)
            .order_by(BookingOptionSelection.id)
        ).all()
        grouped: dict[str, list[dict[str, str]]] = {}
        for item in rows:
            grouped.setdefault(item.group_code_snapshot, []).append(
                {"code": item.item_code_snapshot, "name": item.item_name_snapshot}
            )
        return grouped

    def summary(self, db: Session, booking: Booking) -> dict[str, Any]:
        selections = self._selections(db, booking.id)
        shoot_type = selections.get("shoot_type", [])
        return {
            "booking_no": booking.booking_no,
            "status": booking.status,
            "status_text": STATUS_TEXT.get(booking.status, "状态更新中"),
            "requested_date": booking.requested_date.isoformat(),
            "requested_period_code": booking.requested_period_code,
            "shoot_type": shoot_type[0] if shoot_type else None,
            "updated_at": booking.updated_at.replace(tzinfo=None).isoformat() + "Z",
            "version": booking.version,
        }

    def customer_detail(self, db: Session, booking: Booking) -> dict[str, Any]:
        aad = f"bookings:{booking.booking_no}"
        cleared = booking.sensitive_data_cleared_at is not None
        phone = (
            ""
            if cleared
            else self._cipher.decrypt(booking.contact_phone_ciphertext, f"{aad}:contact_phone")
        )
        slot = db.get(AvailabilitySlot, booking.slot_id) if booking.slot_id else None
        events = db.scalars(
            select(BookingEvent)
            .where(BookingEvent.booking_id == booking.id)
            .order_by(BookingEvent.created_at)
        ).all()
        return {
            **self.summary(db, booking),
            "status_note": STATUS_NOTE.get(booking.status, "请稍后刷新查看。"),
            "participant_count": booking.participant_count,
            "budget_code": booking.budget_code,
            "location": {
                "type": booking.location_type,
                "code": booking.location_code,
                "text": (
                    self._cipher.decrypt(
                        booking.custom_location_ciphertext, f"{aad}:custom_location"
                    )
                    if booking.custom_location_ciphertext
                    else None
                ),
            },
            "contact": {
                "name": (
                    "已清理"
                    if cleared
                    else self._cipher.decrypt(
                        booking.contact_name_ciphertext, f"{aad}:contact_name"
                    )
                ),
                "phone_masked": "已清理" if cleared else f"{phone[:3]}****{phone[-4:]}",
            },
            "remark": (
                self._cipher.decrypt(booking.remark_ciphertext, f"{aad}:remark")
                if booking.remark_ciphertext
                else ""
            ),
            "selections": self._selections(db, booking.id),
            "confirmed_slot": (
                {
                    "start_at": as_shanghai(slot.start_at).isoformat(),
                    "end_at": as_shanghai(slot.end_at).isoformat(),
                    "public_note": slot.public_note,
                }
                if slot
                else None
            ),
            "timeline": [
                {
                    "event_type": event.event_type,
                    "from_status": event.from_status,
                    "to_status": event.to_status,
                    "message": event.public_message,
                    "created_at": event.created_at.isoformat() + "Z",
                }
                for event in events
                if event.public_message or event.to_status
            ],
        }

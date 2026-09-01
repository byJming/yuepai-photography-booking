from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.core.security import FieldCipher
from app.models import AuditLog, AvailabilitySlot, Booking
from app.schemas.booking import AvailabilityBatchRequest
from app.utils.time import as_shanghai, as_utc_naive, utc_now


class AvailabilityService:
    def __init__(self, cipher: FieldCipher) -> None:
        self._cipher = cipher

    def list_month(self, db: Session, month: str) -> list[dict[str, Any]]:
        slots = db.scalars(select(AvailabilitySlot).order_by(AvailabilitySlot.start_at)).all()
        return [
            {
                "id": slot.id,
                "start_at": as_shanghai(slot.start_at).isoformat(),
                "end_at": as_shanghai(slot.end_at).isoformat(),
                "status": slot.status,
                "public_note": slot.public_note,
                "internal_note": (
                    self._cipher.decrypt(
                        slot.internal_note_ciphertext,
                        f"availability.internal:{slot.start_at.isoformat()}:{slot.end_at.isoformat()}",
                    )
                    if slot.internal_note_ciphertext
                    else None
                ),
                "version": slot.version,
                "booking_no": db.scalar(
                    select(Booking.booking_no).where(Booking.slot_id == slot.id)
                ),
            }
            for slot in slots
            if as_shanghai(slot.start_at).strftime("%Y-%m") == month
        ]

    def batch_upsert(
        self,
        db: Session,
        admin_id: int,
        body: AvailabilityBatchRequest,
        request_id: str,
    ) -> dict[str, Any]:
        now = utc_now()
        saved_count = 0
        skipped_confirmed_count = 0
        for item in body.slots:
            start = as_utc_naive(item.start_at)
            end = as_utc_naive(item.end_at)
            if as_shanghai(start).strftime("%Y-%m") != body.month:
                raise ConflictError("档期不属于所选月份。")
            overlapping = db.scalars(
                select(AvailabilitySlot)
                .where(AvailabilitySlot.start_at < end, AvailabilitySlot.end_at > start)
                .with_for_update()
            ).all()
            if any(slot.status == "confirmed" for slot in overlapping):
                skipped_confirmed_count += 1
                continue
            slot = next(
                (
                    candidate
                    for candidate in overlapping
                    if candidate.start_at == start and candidate.end_at == end
                ),
                None,
            )
            other_overlapping = [
                candidate
                for candidate in overlapping
                if slot is None or candidate.id != slot.id
            ]
            if other_overlapping:
                raise ConflictError("所选时段与已有档期重叠，请调整时间后重试。")
            encrypted_note = (
                self._cipher.encrypt(
                    item.internal_note,
                    f"availability.internal:{start.isoformat()}:{end.isoformat()}",
                )
                if item.internal_note
                else None
            )
            if slot is None:
                db.add(
                    AvailabilitySlot(
                        start_at=start,
                        end_at=end,
                        status=item.status,
                        public_note=item.public_note,
                        internal_note_ciphertext=encrypted_note,
                        version=1,
                        created_by_admin_id=admin_id,
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                slot.status = item.status
                slot.public_note = item.public_note
                slot.internal_note_ciphertext = encrypted_note
                slot.version += 1
                slot.updated_at = now
            saved_count += 1
        db.add(
            AuditLog(
                actor_admin_user_id=admin_id,
                action="availability.batch_upsert",
                entity_type="availability_slot",
                entity_id=None,
                request_id=request_id,
                metadata_json={
                    "month": body.month,
                    "slot_count": len(body.slots),
                    "saved_count": saved_count,
                    "skipped_confirmed_count": skipped_confirmed_count,
                },
                created_at=now,
            )
        )
        db.commit()
        return {
            "slots": self.list_month(db, body.month),
            "saved_count": saved_count,
            "skipped_confirmed_count": skipped_confirmed_count,
        }

    def delete_slot(
        self,
        db: Session,
        admin_id: int,
        slot_id: int,
        version: int,
        request_id: str,
    ) -> None:
        slot = db.scalar(
            select(AvailabilitySlot).where(AvailabilitySlot.id == slot_id).with_for_update()
        )
        if slot is None:
            raise NotFoundError("档期不存在。")
        if slot.version != version:
            raise ConflictError("档期已更新，请刷新后重试。")
        booking_exists = db.scalar(select(Booking.id).where(Booking.slot_id == slot.id)) is not None
        if slot.status == "confirmed" or booking_exists:
            raise ConflictError("已确认档期不能删除，请先从对应预约中取消或释放档期。")
        now = utc_now()
        db.add(
            AuditLog(
                actor_admin_user_id=admin_id,
                action="availability.delete",
                entity_type="availability_slot",
                entity_id=slot.id,
                request_id=request_id,
                metadata_json={
                    "start_at": slot.start_at.isoformat(),
                    "end_at": slot.end_at.isoformat(),
                    "status": slot.status,
                },
                created_at=now,
            )
        )
        db.delete(slot)
        db.commit()

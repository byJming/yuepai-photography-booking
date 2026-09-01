from __future__ import annotations

import hashlib
import json
import secrets
from datetime import timedelta
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, DomainValidationError, NotFoundError
from app.core.security import FieldCipher
from app.models import (
    AppSetting,
    AuditLog,
    AvailabilitySlot,
    Booking,
    BookingEvent,
    BookingOptionGroup,
    BookingOptionItem,
    BookingOptionSelection,
    DataDeletionRequest,
)
from app.schemas.booking import (
    AdminBookingActionRequest,
    BookingCancelRequest,
    BookingCreateRequest,
    BookingUpdateRequest,
)
from app.services.booking_state import BookingAction, BookingStatus, next_status
from app.utils.time import as_shanghai, local_today, period_code, utc_now

_BOOKING_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
_ADMIN_ACTIONS = {
    "request_info": BookingAction.REQUEST_INFO,
    "propose_reschedule": BookingAction.PROPOSE_RESCHEDULE,
    "confirm": BookingAction.CONFIRM,
    "decline": BookingAction.DECLINE,
    "complete": BookingAction.COMPLETE,
    "cancel": BookingAction.ADMIN_CANCEL,
}


def _booking_no() -> str:
    day = as_shanghai(utc_now()).strftime("%y%m%d")
    random_part = "".join(secrets.choice(_BOOKING_ALPHABET) for _ in range(8))
    return f"YP{day}{random_part}"


def _fingerprint(body: BookingCreateRequest) -> bytes:
    canonical = json.dumps(
        body.model_dump(mode="json", exclude_none=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).digest()


def _conflict(code: str, message: str) -> ConflictError:
    error = ConflictError(message)
    error.code = code
    return error


class BookingService:
    """预约创建、客户隔离、状态机和确认档期事务边界。"""

    def __init__(self, cipher: FieldCipher) -> None:
        self._cipher = cipher

    def _setting(self, db: Session, key: str, default: Any) -> Any:
        setting = db.get(AppSetting, key)
        return setting.value_json if setting is not None else default

    def _validate_policy(self, db: Session, body: BookingCreateRequest) -> None:
        versions = self._setting(db, "policy_versions", {"privacy": "v1", "service_terms": "v1"})
        if body.privacy_policy_version != versions.get(
            "privacy"
        ) or body.service_terms_version != versions.get("service_terms"):
            error = _conflict("POLICY_VERSION_OUTDATED", "相关说明已更新，请重新阅读后提交。")
            raise error

    def _validate_date_and_slot(
        self, db: Session, requested_date: Any, requested_period_code: str
    ) -> None:
        rules = self._setting(db, "booking_rules", {"open_months": 3})
        today = local_today()
        max_date = today + timedelta(days=int(rules.get("open_months", 3)) * 31)
        if requested_date < today or requested_date > max_date:
            raise DomainValidationError("意向日期不在可预约范围内。")
        slots = db.scalars(select(AvailabilitySlot).where(AvailabilitySlot.status == "open")).all()
        if not any(
            as_shanghai(slot.start_at).date() == requested_date
            and period_code(slot.start_at) == requested_period_code
            for slot in slots
        ):
            raise DomainValidationError("所选日期或时段当前不可约，请重新选择。")

    def _validated_items(
        self, db: Session, selections: dict[str, list[str]]
    ) -> list[tuple[BookingOptionGroup, BookingOptionItem]]:
        groups = db.scalars(
            select(BookingOptionGroup)
            .where(BookingOptionGroup.status == "active")
            .order_by(BookingOptionGroup.sort_order)
        ).all()
        by_code = {group.code: group for group in groups}
        unknown_groups = set(selections) - set(by_code)
        if unknown_groups:
            raise DomainValidationError("预约选项已更新，请刷新页面后重试。")
        selected: list[tuple[BookingOptionGroup, BookingOptionItem]] = []
        for group in groups:
            codes = list(dict.fromkeys(selections.get(group.code, [])))
            if len(codes) < group.min_select or len(codes) > group.max_select:
                raise DomainValidationError(f"“{group.name}”选择数量不符合要求。")
            if group.is_required and not codes:
                raise DomainValidationError(f"请选择“{group.name}”。")
            if not codes:
                continue
            items = db.scalars(
                select(BookingOptionItem).where(
                    BookingOptionItem.group_id == group.id,
                    BookingOptionItem.status == "active",
                    BookingOptionItem.code.in_(codes),
                )
            ).all()
            if len(items) != len(codes):
                raise DomainValidationError("预约选项已更新，请刷新页面后重试。")
            selected.extend((group, item) for item in items)
        return selected

    def create(
        self,
        db: Session,
        user_id: int,
        idempotency_key: str,
        body: BookingCreateRequest,
    ) -> Booking:
        if not 8 <= len(idempotency_key) <= 128:
            raise DomainValidationError("提交标识无效，请返回后重新提交。")
        key_hash = hashlib.sha256(idempotency_key.encode("utf-8")).digest()
        request_hash = _fingerprint(body)
        existing = db.scalar(
            select(Booking).where(
                Booking.user_id == user_id,
                Booking.idempotency_key_hash == key_hash,
            )
        )
        if existing is not None:
            if existing.request_fingerprint != request_hash:
                raise _conflict("IDEMPOTENCY_CONFLICT", "请勿使用同一次提交修改预约内容。")
            return existing
        self._validate_policy(db, body)
        self._validate_date_and_slot(db, body.requested_date, body.requested_period_code)
        selected_items = self._validated_items(db, body.selections)
        now = utc_now()
        number = _booking_no()
        aad_prefix = f"bookings:{number}"
        booking = Booking(
            booking_no=number,
            user_id=user_id,
            idempotency_key_hash=key_hash,
            request_fingerprint=request_hash,
            status=BookingStatus.SUBMITTED.value,
            requested_date=body.requested_date,
            requested_period_code=body.requested_period_code,
            participant_count=body.participant_count,
            budget_code=body.budget_code,
            location_type=body.location.type,
            location_code=body.location.code,
            custom_location_ciphertext=(
                self._cipher.encrypt(body.location.text or "", f"{aad_prefix}:custom_location")
                if body.location.type == "custom"
                else None
            ),
            contact_name_ciphertext=self._cipher.encrypt(
                body.contact.name, f"{aad_prefix}:contact_name"
            ),
            contact_phone_ciphertext=self._cipher.encrypt(
                body.contact.phone, f"{aad_prefix}:contact_phone"
            ),
            contact_phone_last4=body.contact.phone[-4:],
            remark_ciphertext=(
                self._cipher.encrypt(body.remark, f"{aad_prefix}:remark") if body.remark else None
            ),
            privacy_policy_version=body.privacy_policy_version,
            service_terms_version=body.service_terms_version,
            consented_at=now,
            version=1,
            submitted_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(booking)
        db.flush()
        for group, item in selected_items:
            db.add(
                BookingOptionSelection(
                    booking_id=booking.id,
                    option_item_id=item.id,
                    group_code_snapshot=group.code,
                    item_code_snapshot=item.code,
                    item_name_snapshot=item.name,
                    created_at=now,
                )
            )
        db.add(
            BookingEvent(
                booking_id=booking.id,
                actor_user_id=user_id,
                actor_type="customer",
                event_type="submitted",
                to_status=BookingStatus.SUBMITTED.value,
                public_message="预约意向已提交，等待摄影师确认。",
                metadata_json={},
                created_at=now,
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = db.scalar(
                select(Booking).where(
                    Booking.user_id == user_id,
                    Booking.idempotency_key_hash == key_hash,
                )
            )
            if existing is not None and existing.request_fingerprint == request_hash:
                return existing
            raise
        return booking

    def get_for_customer(self, db: Session, user_id: int, booking_no: str) -> Booking:
        booking = db.scalar(
            select(Booking).where(Booking.booking_no == booking_no, Booking.user_id == user_id)
        )
        if booking is None:
            error = NotFoundError("预约不存在。")
            error.code = "BOOKING_NOT_FOUND"
            raise error
        return booking

    def list_for_customer(self, db: Session, user_id: int, limit: int = 10) -> list[Booking]:
        return list(
            db.scalars(
                select(Booking)
                .where(Booking.user_id == user_id)
                .order_by(Booking.updated_at.desc())
                .limit(limit)
            ).all()
        )

    def update(
        self, db: Session, user_id: int, booking_no: str, body: BookingUpdateRequest
    ) -> Booking:
        booking = self.get_for_customer(db, user_id, booking_no)
        if booking.version != body.version:
            raise _conflict("BOOKING_VERSION_CONFLICT", "预约已更新，请刷新后重试。")
        action = BookingAction.CUSTOMER_UPDATE
        try:
            target = next_status(BookingStatus(booking.status), action)
        except ValueError as exc:
            raise _conflict("BOOKING_STATE_CONFLICT", "当前状态不允许修改预约。") from exc
        requested_date = body.requested_date or booking.requested_date
        requested_period = body.requested_period_code or booking.requested_period_code
        self._validate_date_and_slot(db, requested_date, requested_period)
        selected_items = (
            self._validated_items(db, body.selections) if body.selections is not None else None
        )
        now = utc_now()
        booking.requested_date = requested_date
        booking.requested_period_code = requested_period
        if body.participant_count is not None:
            booking.participant_count = body.participant_count
        if "budget_code" in body.model_fields_set:
            booking.budget_code = body.budget_code
        aad_prefix = f"bookings:{booking.booking_no}"
        if body.location is not None:
            booking.location_type = body.location.type
            booking.location_code = body.location.code
            booking.custom_location_ciphertext = (
                self._cipher.encrypt(body.location.text or "", f"{aad_prefix}:custom_location")
                if body.location.type == "custom"
                else None
            )
        if body.contact is not None:
            booking.contact_name_ciphertext = self._cipher.encrypt(
                body.contact.name, f"{aad_prefix}:contact_name"
            )
            booking.contact_phone_ciphertext = self._cipher.encrypt(
                body.contact.phone, f"{aad_prefix}:contact_phone"
            )
            booking.contact_phone_last4 = body.contact.phone[-4:]
        if body.remark is not None:
            booking.remark_ciphertext = (
                self._cipher.encrypt(body.remark, f"{aad_prefix}:remark") if body.remark else None
            )
        if selected_items is not None:
            db.query(BookingOptionSelection).filter(
                BookingOptionSelection.booking_id == booking.id
            ).delete(synchronize_session=False)
            for group, item in selected_items:
                db.add(
                    BookingOptionSelection(
                        booking_id=booking.id,
                        option_item_id=item.id,
                        group_code_snapshot=group.code,
                        item_code_snapshot=item.code,
                        item_name_snapshot=item.name,
                        created_at=now,
                    )
                )
        previous = booking.status
        booking.status = target.value
        booking.version += 1
        booking.updated_at = now
        db.add(
            BookingEvent(
                booking_id=booking.id,
                actor_user_id=user_id,
                actor_type="customer",
                event_type="customer_updated",
                from_status=previous,
                to_status=target.value,
                public_message="客户已更新预约信息。",
                metadata_json={},
                created_at=now,
            )
        )
        db.commit()
        return booking

    def cancel(
        self, db: Session, user_id: int, booking_no: str, body: BookingCancelRequest
    ) -> Booking:
        booking = self.get_for_customer(db, user_id, booking_no)
        if booking.version != body.version:
            raise _conflict("BOOKING_VERSION_CONFLICT", "预约已更新，请刷新后重试。")
        try:
            target = next_status(BookingStatus(booking.status), BookingAction.CUSTOMER_CANCEL)
        except ValueError as exc:
            raise _conflict("BOOKING_STATE_CONFLICT", "当前状态不允许取消预约。") from exc
        now = utc_now()
        previous = booking.status
        booking.status = target.value
        booking.version += 1
        booking.cancelled_at = now
        booking.updated_at = now
        db.add(
            BookingEvent(
                booking_id=booking.id,
                actor_user_id=user_id,
                actor_type="customer",
                event_type="customer_cancelled",
                from_status=previous,
                to_status=target.value,
                public_message="客户已取消预约意向。",
                metadata_json={"reason_code": "customer_cancelled"},
                created_at=now,
            )
        )
        db.commit()
        return booking

    def _admin_booking_query(self, booking_no: str) -> Select[tuple[Booking]]:
        return select(Booking).where(Booking.booking_no == booking_no).with_for_update()

    def admin_action(
        self,
        db: Session,
        admin_id: int,
        booking_no: str,
        body: AdminBookingActionRequest,
        request_id: str,
    ) -> Booking:
        booking = db.scalar(self._admin_booking_query(booking_no))
        if booking is None:
            raise NotFoundError("预约不存在。")
        if booking.version != body.version:
            raise _conflict("BOOKING_VERSION_CONFLICT", "预约已更新，请刷新后重试。")
        action = _ADMIN_ACTIONS[body.action]
        try:
            target = next_status(BookingStatus(booking.status), action)
        except ValueError as exc:
            raise _conflict("BOOKING_STATE_CONFLICT", "当前状态不允许执行该操作。") from exc
        now = utc_now()
        metadata: dict[str, Any] = {}
        if action is BookingAction.CONFIRM:
            slot = db.scalar(
                select(AvailabilitySlot)
                .where(AvailabilitySlot.id == body.slot_id)
                .with_for_update()
            )
            if slot is None or slot.status != "open":
                raise _conflict("BOOKING_SLOT_CONFLICT", "该档期已不可用，请选择其他时间。")
            if db.scalar(select(Booking.id).where(Booking.slot_id == slot.id)) is not None:
                raise _conflict("BOOKING_SLOT_CONFLICT", "该档期已经确认了其他预约。")
            booking.slot_id = slot.id
            booking.confirmed_at = now
            slot.status = "confirmed"
            slot.version += 1
            slot.updated_at = now
            metadata = {
                "slot_id": slot.id,
                "start_at": slot.start_at.isoformat(),
                "end_at": slot.end_at.isoformat(),
            }
        elif action is BookingAction.COMPLETE:
            booking.completed_at = now
        elif action is BookingAction.ADMIN_CANCEL:
            booking.cancelled_at = now
            if booking.slot_id is not None:
                slot = db.scalar(
                    select(AvailabilitySlot)
                    .where(AvailabilitySlot.id == booking.slot_id)
                    .with_for_update()
                )
                if slot is not None:
                    metadata = {
                        "released_slot_id": slot.id,
                        "start_at": slot.start_at.isoformat(),
                        "end_at": slot.end_at.isoformat(),
                    }
                    slot.status = "open" if body.reopen_slot else "blocked"
                    slot.version += 1
                    slot.updated_at = now
                booking.slot_id = None
        previous = booking.status
        booking.status = target.value
        booking.version += 1
        booking.updated_at = now
        internal_aad = f"booking_events.internal:{booking.booking_no}:{now.isoformat()}"
        if body.internal_note:
            metadata["internal_aad"] = internal_aad
        db.add(
            BookingEvent(
                booking_id=booking.id,
                actor_admin_user_id=admin_id,
                actor_type="admin",
                event_type=body.action,
                from_status=previous,
                to_status=target.value,
                public_message=body.public_message or None,
                internal_note_ciphertext=(
                    self._cipher.encrypt(
                        body.internal_note,
                        internal_aad,
                    )
                    if body.internal_note
                    else None
                ),
                metadata_json=metadata,
                created_at=now,
            )
        )
        db.add(
            AuditLog(
                actor_admin_user_id=admin_id,
                action=f"booking.{body.action}",
                entity_type="booking",
                entity_id=booking.id,
                request_id=request_id,
                metadata_json={"booking_no": booking.booking_no, "target_status": target.value},
                created_at=now,
            )
        )
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise _conflict("BOOKING_SLOT_CONFLICT", "该档期已经确认了其他预约。") from exc
        return booking

    def request_data_deletion(self, db: Session, user_id: int) -> DataDeletionRequest:
        existing = db.scalar(
            select(DataDeletionRequest).where(
                DataDeletionRequest.user_id == user_id,
                DataDeletionRequest.status == "pending",
            )
        )
        if existing is not None:
            return existing
        now = utc_now()
        request = DataDeletionRequest(
            user_id=user_id,
            status="pending",
            created_at=now,
            updated_at=now,
        )
        db.add(request)
        db.commit()
        return request

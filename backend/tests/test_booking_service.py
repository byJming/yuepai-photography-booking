import base64
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.errors import ConflictError, NotFoundError
from app.core.security import FieldCipher
from app.models import (
    AdminUser,
    AppSetting,
    AvailabilitySlot,
    BookingEvent,
    BookingOptionGroup,
    BookingOptionItem,
    User,
)
from app.schemas.booking import (
    AdminBookingActionRequest,
    BookingCancelRequest,
    BookingCreateRequest,
)
from app.services.bookings import BookingService

SHANGHAI = ZoneInfo("Asia/Shanghai")


def build_db() -> tuple[Session, User, User, AdminUser, AvailabilitySlot]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    now = datetime.now(UTC).replace(tzinfo=None)
    first = User(
        openid_hash=b"a" * 32,
        openid_ciphertext=b"cipher",
        status="active",
        last_login_at=now,
        created_at=now,
        updated_at=now,
    )
    second = User(
        openid_hash=b"b" * 32,
        openid_ciphertext=b"cipher",
        status="active",
        last_login_at=now,
        created_at=now,
        updated_at=now,
    )
    admin = AdminUser(
        username="owner",
        password_hash="hash",  # noqa: S106
        totp_secret_ciphertext=b"cipher",
        status="active",
        failed_login_count=0,
        password_changed_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add_all([first, second, admin])
    db.flush()
    group = BookingOptionGroup(
        code="shoot_type",
        name="拍摄类型",
        selection_mode="single",
        is_required=True,
        min_select=1,
        max_select=1,
        status="active",
        sort_order=1,
        created_at=now,
        updated_at=now,
    )
    db.add(group)
    db.flush()
    db.add(
        BookingOptionItem(
            group_id=group.id,
            code="portrait",
            name="个人写真",
            description="",
            metadata_json={},
            status="active",
            sort_order=1,
            created_at=now,
            updated_at=now,
        )
    )
    local_start = (datetime.now(SHANGHAI) + timedelta(days=1)).replace(
        hour=14, minute=30, second=0, microsecond=0
    )
    slot = AvailabilitySlot(
        start_at=local_start.astimezone(UTC).replace(tzinfo=None),
        end_at=(local_start + timedelta(hours=2)).astimezone(UTC).replace(tzinfo=None),
        status="open",
        public_note=None,
        version=1,
        created_by_admin_id=admin.id,
        created_at=now,
        updated_at=now,
    )
    db.add(slot)
    db.add_all(
        [
            AppSetting(
                setting_key="policy_versions",
                value_json={"privacy": "v1", "service_terms": "v1"},
                is_public=True,
                updated_at=now,
            ),
            AppSetting(
                setting_key="booking_rules",
                value_json={"open_months": 3, "confirmed_customer_cancel": False},
                is_public=False,
                updated_at=now,
            ),
        ]
    )
    db.commit()
    return db, first, second, admin, slot


def booking_request(slot: AvailabilitySlot, remark: str = "") -> BookingCreateRequest:
    requested_date = slot.start_at.replace(tzinfo=UTC).astimezone(SHANGHAI).date()
    return BookingCreateRequest.model_validate(
        {
            "requested_date": requested_date.isoformat(),
            "requested_period_code": "afternoon",
            "participant_count": 1,
            "location": {"type": "preset", "code": "city"},
            "selections": {"shoot_type": ["portrait"]},
            "contact": {"name": "测试客户", "phone": "13800138000"},
            "remark": remark,
            "privacy_policy_version": "v1",
            "service_terms_version": "v1",
        }
    )


def service() -> BookingService:
    return BookingService(FieldCipher(base64.b64encode(b"x" * 32).decode()))


def test_create_booking_is_idempotent() -> None:
    db, user, _, _, slot = build_db()
    first = service().create(db, user.id, "same-idempotency-key", booking_request(slot))
    second = service().create(db, user.id, "same-idempotency-key", booking_request(slot))

    assert first.id == second.id
    assert first.booking_no == second.booking_no


def test_reused_idempotency_key_with_other_payload_conflicts() -> None:
    db, user, _, _, slot = build_db()
    service().create(db, user.id, "same-idempotency-key", booking_request(slot))

    with pytest.raises(ConflictError) as caught:
        service().create(db, user.id, "same-idempotency-key", booking_request(slot, "不同内容"))
    assert caught.value.code == "IDEMPOTENCY_CONFLICT"


def test_customer_cannot_read_another_users_booking() -> None:
    db, first_user, second_user, _, slot = build_db()
    booking = service().create(db, first_user.id, "first-key", booking_request(slot))

    with pytest.raises(NotFoundError):
        service().get_for_customer(db, second_user.id, booking.booking_no)


def test_only_one_booking_can_confirm_same_slot() -> None:
    db, first_user, second_user, admin, slot = build_db()
    first = service().create(db, first_user.id, "first-key", booking_request(slot))
    second = service().create(db, second_user.id, "second-key", booking_request(slot))
    action = AdminBookingActionRequest(
        action="confirm", version=first.version, slot_id=slot.id, public_message="已确认"
    )
    service().admin_action(db, admin.id, first.booking_no, action, "request-1")

    with pytest.raises(ConflictError) as caught:
        service().admin_action(
            db,
            admin.id,
            second.booking_no,
            action.model_copy(update={"version": second.version}),
            "request-2",
        )
    assert caught.value.code == "BOOKING_SLOT_CONFLICT"


def test_customer_cancel_does_not_store_customer_supplied_notes() -> None:
    db, user, _, _, slot = build_db()
    booking = service().create(db, user.id, "cancel-key", booking_request(slot))

    cancelled = service().cancel(
        db,
        user.id,
        booking.booking_no,
        BookingCancelRequest.model_validate(
            {
                "version": booking.version,
                "reason_code": "schedule_changed",
                "reason_text": "不应进入后台的任意文本",
            }
        ),
    )

    assert cancelled.status == "cancelled_by_user"
    event = db.scalar(
        select(BookingEvent).where(
            BookingEvent.booking_id == booking.id,
            BookingEvent.event_type == "customer_cancelled",
        )
    )
    assert event is not None
    assert event.internal_note_ciphertext is None
    assert event.metadata_json == {"reason_code": "customer_cancelled"}

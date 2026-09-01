import base64
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.errors import ConflictError
from app.core.security import FieldCipher
from app.models import (
    AdminUser,
    AppSetting,
    Booking,
    BookingEvent,
    DataDeletionRequest,
    User,
)
from app.services.data_retention import DataRetentionService


def cipher() -> FieldCipher:
    return FieldCipher(base64.b64encode(b"r" * 32).decode())


def build_db() -> tuple[Session, User, AdminUser]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    now = datetime.now(UTC).replace(tzinfo=None)
    user = User(
        openid_hash=b"u" * 32,
        openid_ciphertext=b"encrypted-openid",
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
    db.add_all([user, admin])
    db.flush()
    db.add(
        AppSetting(
            setting_key="booking_rules",
            value_json={
                "data_retention_completed_months": 12,
                "data_retention_cancelled_months": 6,
            },
            is_public=False,
            updated_at=now,
        )
    )
    db.commit()
    return db, user, admin


def add_booking(
    db: Session,
    user: User,
    *,
    booking_no: str,
    status: str,
    changed_at: datetime,
) -> Booking:
    aad = f"bookings:{booking_no}"
    field_cipher = cipher()
    booking = Booking(
        booking_no=booking_no,
        user_id=user.id,
        idempotency_key_hash=booking_no.encode().ljust(32, b"0")[:32],
        request_fingerprint=booking_no.encode().ljust(32, b"1")[:32],
        status=status,
        requested_date=date.today(),
        requested_period_code="afternoon",
        participant_count=1,
        budget_code="budget_300_500",
        location_type="custom",
        location_code="custom",
        custom_location_ciphertext=field_cipher.encrypt("测试地点", f"{aad}:custom_location"),
        contact_name_ciphertext=field_cipher.encrypt("测试客户", f"{aad}:contact_name"),
        contact_phone_ciphertext=field_cipher.encrypt("13800138000", f"{aad}:contact_phone"),
        contact_phone_last4="8000",
        remark_ciphertext=field_cipher.encrypt("包含个人偏好", f"{aad}:remark"),
        privacy_policy_version="v1",
        service_terms_version="v1",
        consented_at=changed_at,
        version=1,
        submitted_at=changed_at,
        completed_at=changed_at if status == "completed" else None,
        cancelled_at=changed_at if status.startswith("cancelled") or status == "declined" else None,
        created_at=changed_at,
        updated_at=changed_at,
    )
    db.add(booking)
    db.flush()
    db.add(
        BookingEvent(
            booking_id=booking.id,
            actor_type="admin",
            event_type="status_changed",
            to_status=status,
            public_message="可能包含地点的说明",
            internal_note_ciphertext=b"encrypted-note",
            metadata_json={"internal_aad": "sensitive"},
            created_at=changed_at,
        )
    )
    db.commit()
    return booking


def test_policy_cleanup_only_anonymizes_expired_bookings() -> None:
    db, user, _ = build_db()
    now = datetime.now(UTC).replace(tzinfo=None)
    expired = add_booking(
        db,
        user,
        booking_no="20250101000001",
        status="completed",
        changed_at=now - timedelta(days=380),
    )
    recent = add_booking(
        db,
        user,
        booking_no="20260101000002",
        status="cancelled_by_user",
        changed_at=now - timedelta(days=30),
    )

    result = DataRetentionService(cipher()).run_policy_cleanup(db, now=now)
    db.refresh(expired)
    db.refresh(recent)

    assert result == {"bookings_anonymized": 1}
    assert expired.sensitive_data_cleared_at == now
    assert expired.contact_phone_last4 == "0000"
    assert expired.custom_location_ciphertext is None
    assert expired.remark_ciphertext is None
    assert recent.sensitive_data_cleared_at is None
    event = db.query(BookingEvent).filter_by(booking_id=expired.id).one()
    assert event.public_message is None
    assert event.internal_note_ciphertext is None
    assert event.metadata_json == {}


def test_deletion_request_anonymizes_user_and_all_bookings() -> None:
    db, user, admin = build_db()
    now = datetime.now(UTC).replace(tzinfo=None)
    booking = add_booking(
        db,
        user,
        booking_no="20250101000003",
        status="completed",
        changed_at=now - timedelta(days=10),
    )
    request = DataDeletionRequest(
        user_id=user.id,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    db.add(request)
    db.commit()

    result = DataRetentionService(cipher()).complete_deletion_request(
        db, request.id, admin.id, "request-id", now=now
    )
    db.refresh(user)
    db.refresh(booking)
    db.refresh(request)

    assert result.id == request.id
    assert request.status == "completed"
    assert request.processed_by_admin_id == admin.id
    assert user.status == "anonymized"
    assert user.openid_ciphertext is None
    assert user.openid_hash != b"u" * 32
    assert booking.sensitive_data_cleared_at == now


def test_deletion_request_is_blocked_while_booking_is_active() -> None:
    db, user, admin = build_db()
    now = datetime.now(UTC).replace(tzinfo=None)
    add_booking(
        db,
        user,
        booking_no="20260726000004",
        status="confirmed",
        changed_at=now,
    )
    request = DataDeletionRequest(
        user_id=user.id,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    db.add(request)
    db.commit()

    with pytest.raises(ConflictError) as caught:
        DataRetentionService(cipher()).complete_deletion_request(
            db, request.id, admin.id, "request-id", now=now
        )

    assert caught.value.code == "DATA_DELETION_ACTIVE_BOOKINGS"

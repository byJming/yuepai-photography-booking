import base64
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.security import FieldCipher
from app.models import Booking, User
from app.services.admin_bookings import AdminBookingService
from app.utils.time import local_today


def make_booking(
    cipher: FieldCipher,
    user_id: int,
    booking_no: str,
    status: str,
    fingerprint: bytes,
    now: datetime,
) -> Booking:
    aad = f"bookings:{booking_no}"
    return Booking(
        booking_no=booking_no,
        user_id=user_id,
        idempotency_key_hash=fingerprint,
        request_fingerprint=fingerprint,
        status=status,
        requested_date=local_today(),
        requested_period_code="afternoon",
        participant_count=1,
        location_type="preset",
        location_code="studio",
        contact_name_ciphertext=cipher.encrypt("测试客户", f"{aad}:contact_name"),
        contact_phone_ciphertext=cipher.encrypt("13800000000", f"{aad}:contact_phone"),
        contact_phone_last4="0000",
        privacy_policy_version="v1",
        service_terms_version="v1",
        consented_at=now,
        version=1,
        submitted_at=now,
        confirmed_at=now if status == "confirmed" else None,
        created_at=now,
        updated_at=now,
    )


def test_dashboard_includes_today_confirmed_count() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    cipher = FieldCipher(base64.b64encode(b"d" * 32).decode())
    now = datetime.now(UTC).replace(tzinfo=None)
    user = User(
        openid_hash=b"u" * 32,
        openid_ciphertext=b"cipher",
        status="active",
        last_login_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.flush()
    db.add_all(
        [
            make_booking(cipher, user.id, "YP202607260001", "confirmed", b"a" * 32, now),
            make_booking(cipher, user.id, "YP202607260002", "submitted", b"b" * 32, now),
        ]
    )
    db.commit()

    result = AdminBookingService(cipher).dashboard(db)

    assert result["today_confirmed_count"] == 1
    assert result["pending_count"] == 1

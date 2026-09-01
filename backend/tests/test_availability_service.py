import base64
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.errors import ConflictError
from app.core.security import FieldCipher
from app.models import AdminUser, AvailabilitySlot
from app.schemas.booking import AvailabilityBatchRequest
from app.services.availability import AvailabilityService
from app.utils.time import SHANGHAI


def test_admin_month_list_decrypts_internal_note() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    cipher = FieldCipher(base64.b64encode(b"a" * 32).decode())
    now = datetime(2026, 7, 26, tzinfo=UTC).replace(tzinfo=None)
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
    db.add(admin)
    db.flush()
    start = datetime(2026, 8, 10, 6, 30)
    end = datetime(2026, 8, 10, 9, 0)
    aad = f"availability.internal:{start.isoformat()}:{end.isoformat()}"
    db.add(
        AvailabilitySlot(
            start_at=start,
            end_at=end,
            status="open",
            public_note="建议提前十分钟到达",
            internal_note_ciphertext=cipher.encrypt("仅管理员可见", aad),
            version=1,
            created_by_admin_id=admin.id,
            created_at=now,
            updated_at=now,
        )
    )
    db.commit()

    slots = AvailabilityService(cipher).list_month(db, "2026-08")

    assert slots[0]["internal_note"] == "仅管理员可见"
    assert slots[0]["public_note"] == "建议提前十分钟到达"


def test_batch_upsert_skips_confirmed_slots_and_saves_other_dates() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    cipher = FieldCipher(base64.b64encode(b"a" * 32).decode())
    now = datetime(2026, 7, 27, tzinfo=UTC).replace(tzinfo=None)
    admin = AdminUser(
        username="owner",
        password_hash="hash",  # noqa: S106
        status="active",
        failed_login_count=0,
        password_changed_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(admin)
    db.flush()
    db.add(
        AvailabilitySlot(
            start_at=datetime(2026, 8, 10, 6, 30),
            end_at=datetime(2026, 8, 10, 9, 0),
            status="confirmed",
            version=2,
            created_by_admin_id=admin.id,
            created_at=now,
            updated_at=now,
        )
    )
    db.commit()
    request = AvailabilityBatchRequest.model_validate(
        {
            "month": "2026-08",
            "slots": [
                {
                    "start_at": datetime(2026, 8, 10, 14, 30, tzinfo=SHANGHAI),
                    "end_at": datetime(2026, 8, 10, 17, 0, tzinfo=SHANGHAI),
                    "status": "blocked",
                },
                {
                    "start_at": datetime(2026, 8, 11, 14, 30, tzinfo=SHANGHAI),
                    "end_at": datetime(2026, 8, 11, 17, 0, tzinfo=SHANGHAI),
                    "status": "open",
                },
            ],
        }
    )

    result = AvailabilityService(cipher).batch_upsert(db, admin.id, request, "request-id")

    assert result["saved_count"] == 1
    assert result["skipped_confirmed_count"] == 1
    assert [(slot["status"], slot["version"]) for slot in result["slots"]] == [
        ("confirmed", 2),
        ("open", 1),
    ]


def test_batch_upsert_skips_ranges_overlapping_confirmed_slots() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    cipher = FieldCipher(base64.b64encode(b"a" * 32).decode())
    now = datetime(2026, 7, 27, tzinfo=UTC).replace(tzinfo=None)
    admin = AdminUser(
        username="owner",
        password_hash="hash",  # noqa: S106
        status="active",
        failed_login_count=0,
        password_changed_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(admin)
    db.flush()
    db.add(
        AvailabilitySlot(
            start_at=datetime(2026, 8, 10, 6, 30),
            end_at=datetime(2026, 8, 10, 9, 0),
            status="confirmed",
            version=1,
            created_by_admin_id=admin.id,
            created_at=now,
            updated_at=now,
        )
    )
    db.commit()
    request = AvailabilityBatchRequest.model_validate(
        {
            "month": "2026-08",
            "slots": [
                {
                    "start_at": datetime(2026, 8, 10, 15, 0, tzinfo=SHANGHAI),
                    "end_at": datetime(2026, 8, 10, 17, 30, tzinfo=SHANGHAI),
                    "status": "open",
                }
            ],
        }
    )

    result = AvailabilityService(cipher).batch_upsert(db, admin.id, request, "request-id")

    assert result["saved_count"] == 0
    assert result["skipped_confirmed_count"] == 1
    assert len(result["slots"]) == 1


def test_unconfirmed_slot_can_be_deleted_with_matching_version() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    cipher = FieldCipher(base64.b64encode(b"a" * 32).decode())
    now = datetime(2026, 7, 27, tzinfo=UTC).replace(tzinfo=None)
    admin = AdminUser(
        username="owner",
        password_hash="hash",  # noqa: S106
        status="active",
        failed_login_count=0,
        password_changed_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(admin)
    db.flush()
    slot = AvailabilitySlot(
        start_at=datetime(2026, 8, 10, 6, 30),
        end_at=datetime(2026, 8, 10, 9, 0),
        status="blocked",
        version=3,
        created_by_admin_id=admin.id,
        created_at=now,
        updated_at=now,
    )
    db.add(slot)
    db.commit()
    slot_id = slot.id

    AvailabilityService(cipher).delete_slot(db, admin.id, slot_id, 3, "request-id")

    assert db.get(AvailabilitySlot, slot_id) is None


def test_confirmed_slot_cannot_be_deleted() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    cipher = FieldCipher(base64.b64encode(b"a" * 32).decode())
    now = datetime(2026, 7, 27, tzinfo=UTC).replace(tzinfo=None)
    admin = AdminUser(
        username="owner",
        password_hash="hash",  # noqa: S106
        status="active",
        failed_login_count=0,
        password_changed_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(admin)
    db.flush()
    slot = AvailabilitySlot(
        start_at=datetime(2026, 8, 10, 6, 30),
        end_at=datetime(2026, 8, 10, 9, 0),
        status="confirmed",
        version=1,
        created_by_admin_id=admin.id,
        created_at=now,
        updated_at=now,
    )
    db.add(slot)
    db.commit()

    with pytest.raises(ConflictError, match="已确认档期不能删除"):
        AvailabilityService(cipher).delete_slot(db, admin.id, slot.id, 1, "request-id")

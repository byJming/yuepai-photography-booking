import base64
from datetime import UTC, datetime

import fakeredis
import pyotp
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.security import FieldCipher, hash_password
from app.models import AdminUser
from app.services.auth import AdminAuthService, CustomerAuthService
from app.services.sessions import AdminSessionService, CustomerSessionService


def build_db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_customer_login_reuses_internal_user() -> None:
    db = build_db()
    redis = fakeredis.FakeRedis(decode_responses=True)
    sessions = CustomerSessionService(redis, "yuepai:test", "s" * 32, 3600)
    cipher = FieldCipher(base64.b64encode(b"x" * 32).decode())
    service = CustomerAuthService(sessions, cipher, "h" * 32)

    first = service.login(db, "same-openid")
    second = service.login(db, "same-openid")

    assert first.user_id == second.user_id
    assert first.access_token != second.access_token


def test_admin_login_requires_password_and_current_totp() -> None:
    db = build_db()
    redis = fakeredis.FakeRedis(decode_responses=True)
    sessions = AdminSessionService(redis, "yuepai:test", "a" * 32, 3600, 1800)
    cipher = FieldCipher(base64.b64encode(b"x" * 32).decode())
    secret = pyotp.random_base32()
    now = datetime.now(UTC).replace(tzinfo=None)
    admin = AdminUser(
        username="owner",
        password_hash=hash_password("very-strong-password"),
        totp_secret_ciphertext=cipher.encrypt(secret, "admin_users.totp:owner"),
        totp_enabled=True,
        status="active",
        failed_login_count=0,
        password_changed_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(admin)
    db.commit()
    service = AdminAuthService(sessions, cipher)

    result = service.login(db, "owner", "very-strong-password", pyotp.TOTP(secret).now())

    assert result.admin_user_id == admin.id
    assert result.session_token
    assert result.csrf_token


def test_admin_login_without_totp_when_disabled() -> None:
    db = build_db()
    redis = fakeredis.FakeRedis(decode_responses=True)
    sessions = AdminSessionService(redis, "yuepai:test", "a" * 32, 3600, 1800)
    cipher = FieldCipher(base64.b64encode(b"x" * 32).decode())
    now = datetime.now(UTC).replace(tzinfo=None)
    admin = AdminUser(
        username="owner",
        password_hash=hash_password("very-strong-password"),
        totp_secret_ciphertext=None,
        totp_enabled=False,
        status="active",
        failed_login_count=0,
        password_changed_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(admin)
    db.commit()
    service = AdminAuthService(sessions, cipher)

    result = service.login(db, "owner", "very-strong-password", None)

    assert result.admin_user_id == admin.id
    assert result.totp_enabled is False


def test_admin_login_uses_uniform_failure() -> None:
    db = build_db()
    redis = fakeredis.FakeRedis(decode_responses=True)
    sessions = AdminSessionService(redis, "yuepai:test", "a" * 32, 3600, 1800)
    cipher = FieldCipher(base64.b64encode(b"x" * 32).decode())
    service = AdminAuthService(sessions, cipher)

    result = service.try_login(db, "missing", "wrong-password", "000000")

    assert result is None

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pyotp
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AuthenticationError
from app.core.security import FieldCipher, hash_password, hmac_bytes, verify_password
from app.models import AdminUser, User
from app.services.sessions import AdminSessionService, CustomerSessionService

_DUMMY_PASSWORD_HASH = hash_password("dummy-password-used-only-for-timing")


class AdminAuthenticationError(AuthenticationError):
    code = "ADMIN_AUTH_FAILED"
    message = "账号或验证信息不正确。"


@dataclass(frozen=True)
class CustomerLoginResult:
    user_id: int
    access_token: str
    expires_in: int


@dataclass(frozen=True)
class AdminLoginResult:
    admin_user_id: int
    username: str
    session_token: str
    csrf_token: str
    totp_enabled: bool


def verify_admin_totp(admin: AdminUser, cipher: FieldCipher, totp_code: str | None) -> int | None:
    if not totp_code or admin.totp_secret_ciphertext is None:
        return None
    try:
        secret = cipher.decrypt(
            admin.totp_secret_ciphertext,
            f"admin_users.totp:{admin.username}",
        )
        totp = pyotp.TOTP(secret)
        aware_now = datetime.now(UTC)
        if not totp.verify(totp_code, for_time=aware_now, valid_window=1):
            return None
        return int(totp.timecode(aware_now))
    except (ValueError, TypeError):
        return None


class CustomerAuthService:
    def __init__(
        self,
        sessions: CustomerSessionService,
        cipher: FieldCipher,
        openid_hmac_key: str,
        session_ttl_seconds: int = 604_800,
    ) -> None:
        self._sessions = sessions
        self._cipher = cipher
        self._openid_hmac_key = openid_hmac_key
        self._session_ttl = session_ttl_seconds

    def login(self, db: Session, openid: str) -> CustomerLoginResult:
        now = datetime.now(UTC).replace(tzinfo=None)
        openid_hash = hmac_bytes(openid, self._openid_hmac_key)
        user = db.scalar(select(User).where(User.openid_hash == openid_hash))
        if user is None:
            user = User(
                openid_hash=openid_hash,
                openid_ciphertext=self._cipher.encrypt(openid, f"users.openid:{openid_hash.hex()}"),
                status="active",
                last_login_at=now,
                created_at=now,
                updated_at=now,
            )
            db.add(user)
            db.flush()
        elif user.status != "active":
            raise AuthenticationError("当前账号不可用。")
        else:
            user.last_login_at = now
            user.updated_at = now
        db.commit()
        return CustomerLoginResult(
            user_id=user.id,
            access_token=self._sessions.create(user.id),
            expires_in=self._session_ttl,
        )


class AdminAuthService:
    def __init__(self, sessions: AdminSessionService, cipher: FieldCipher) -> None:
        self._sessions = sessions
        self._cipher = cipher

    def try_login(
        self, db: Session, username: str, password: str, totp_code: str | None
    ) -> AdminLoginResult | None:
        now = datetime.now(UTC).replace(tzinfo=None)
        admin = db.scalar(select(AdminUser).where(AdminUser.username == username))
        if admin is None:
            verify_password(_DUMMY_PASSWORD_HASH, password)
            return None
        if admin.status != "active" or (admin.locked_until and admin.locked_until > now):
            verify_password(admin.password_hash, password)
            return None
        password_ok = verify_password(admin.password_hash, password)
        totp_step: int | None = None
        totp_ok = not admin.totp_enabled
        if password_ok and admin.totp_enabled:
            totp_step = verify_admin_totp(admin, self._cipher, totp_code)
            totp_ok = totp_step is not None
        if not password_ok or not totp_ok:
            admin.failed_login_count += 1
            if admin.failed_login_count >= 5:
                admin.locked_until = now + timedelta(minutes=15)
                admin.failed_login_count = 0
            admin.updated_at = now
            db.commit()
            return None
        if totp_step is not None and not self._sessions.consume_totp_step(admin.id, totp_step):
            return None
        admin.failed_login_count = 0
        admin.locked_until = None
        admin.last_login_at = now
        admin.updated_at = now
        db.commit()
        session_token, csrf_token = self._sessions.create(admin.id, totp_step=totp_step)
        return AdminLoginResult(
            admin_user_id=admin.id,
            username=admin.username,
            session_token=session_token,
            csrf_token=csrf_token,
            totp_enabled=admin.totp_enabled,
        )

    def login(
        self, db: Session, username: str, password: str, totp_code: str | None
    ) -> AdminLoginResult:
        result = self.try_login(db, username, password, totp_code)
        if result is None:
            raise AdminAuthenticationError()
        return result
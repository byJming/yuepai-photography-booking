from __future__ import annotations

import hmac
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from app.core.security import hash_secret, new_token


class RedisLike(Protocol):
    def setex(self, name: str, time: int, value: str) -> object: ...

    def get(self, name: str) -> str | bytes | None: ...

    def delete(self, *names: str) -> object: ...

    def expire(self, name: str, time: int) -> object: ...

    def set(
        self,
        name: str,
        value: str,
        ex: int | None = None,
        nx: bool = False,
    ) -> object: ...

    def scan_iter(self, match: str) -> Iterable[str | bytes]: ...


def _decode(value: str | bytes) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else value


class CustomerSessionService:
    def __init__(self, redis: RedisLike, prefix: str, pepper: str, ttl_seconds: int) -> None:
        self._redis = redis
        self._prefix = prefix.rstrip(":")
        self._pepper = pepper
        self._ttl = ttl_seconds

    def _key(self, token: str) -> str:
        return f"{self._prefix}:session:{hash_secret(token, self._pepper)}"

    def create(self, user_id: int) -> str:
        token = new_token()
        payload = json.dumps(
            {"user_id": user_id, "issued_at": datetime.now(UTC).isoformat()},
            separators=(",", ":"),
        )
        self._redis.setex(self._key(token), self._ttl, payload)
        return token

    def get_user_id(self, token: str) -> int | None:
        raw = self._redis.get(self._key(token))
        if raw is None:
            return None
        try:
            return int(json.loads(_decode(raw))["user_id"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def delete(self, token: str) -> None:
        self._redis.delete(self._key(token))


@dataclass(frozen=True)
class AdminSession:
    admin_user_id: int
    issued_at: datetime
    expires_at: datetime
    totp_step: int | None


class AdminSessionService:
    def __init__(
        self,
        redis: RedisLike,
        prefix: str,
        pepper: str,
        absolute_ttl_seconds: int,
        idle_ttl_seconds: int,
    ) -> None:
        self._redis = redis
        self._prefix = prefix.rstrip(":")
        self._pepper = pepper
        self._absolute_ttl = absolute_ttl_seconds
        self._idle_ttl = idle_ttl_seconds

    def _key(self, token: str) -> str:
        return f"{self._prefix}:admin_session:{hash_secret(token, self._pepper)}"

    def _csrf_hash(self, csrf_token: str) -> str:
        return hash_secret(csrf_token, self._pepper)

    def create(self, admin_user_id: int, *, totp_step: int | None = None) -> tuple[str, str]:
        token = new_token()
        csrf_token = new_token()
        issued_at = datetime.now(UTC)
        expires_at = issued_at + timedelta(seconds=self._absolute_ttl)
        payload = json.dumps(
            {
                "admin_user_id": admin_user_id,
                "issued_at": issued_at.isoformat(),
                "expires_at": expires_at.isoformat(),
                "csrf_hash": self._csrf_hash(csrf_token),
                "totp_step": totp_step,
            },
            separators=(",", ":"),
        )
        self._redis.setex(self._key(token), min(self._idle_ttl, self._absolute_ttl), payload)
        return token, csrf_token

    def _read(self, token: str, *, touch: bool) -> tuple[AdminSession, dict[str, object]] | None:
        key = self._key(token)
        raw = self._redis.get(key)
        if raw is None:
            return None
        try:
            payload = json.loads(_decode(raw))
            issued_at = datetime.fromisoformat(str(payload["issued_at"]))
            expires_at = datetime.fromisoformat(str(payload["expires_at"]))
            admin_user_id = int(payload["admin_user_id"])
            raw_totp_step = payload.get("totp_step")
            totp_step = int(raw_totp_step) if raw_totp_step is not None else None
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self._redis.delete(key)
            return None
        now = datetime.now(UTC)
        if expires_at <= now:
            self._redis.delete(key)
            return None
        if touch:
            remaining = max(1, int((expires_at - now).total_seconds()))
            self._redis.expire(key, min(self._idle_ttl, remaining))
        return AdminSession(admin_user_id, issued_at, expires_at, totp_step), payload

    def get(self, token: str) -> AdminSession | None:
        found = self._read(token, touch=True)
        return found[0] if found else None

    def verify_csrf(self, token: str, csrf_token: str) -> bool:
        found = self._read(token, touch=False)
        if found is None:
            return False
        stored = str(found[1].get("csrf_hash", ""))
        return hmac.compare_digest(stored, self._csrf_hash(csrf_token))

    def refresh_csrf(self, token: str) -> str | None:
        found = self._read(token, touch=False)
        if found is None:
            return None
        session, payload = found
        csrf_token = new_token()
        payload["csrf_hash"] = self._csrf_hash(csrf_token)
        remaining = max(1, int((session.expires_at - datetime.now(UTC)).total_seconds()))
        self._redis.setex(
            self._key(token),
            min(self._idle_ttl, remaining),
            json.dumps(payload, separators=(",", ":")),
        )
        return csrf_token

    def delete(self, token: str) -> None:
        self._redis.delete(self._key(token))

    def consume_totp_step(self, admin_user_id: int, step: int) -> bool:
        key = f"{self._prefix}:admin_totp_used:{admin_user_id}:{step}"
        return bool(self._redis.set(key, "1", ex=120, nx=True))

    def delete_all_for_admin(self, admin_user_id: int) -> int:
        deleted = 0
        for raw_key in self._redis.scan_iter(match=f"{self._prefix}:admin_session:*"):
            key = _decode(raw_key)
            raw = self._redis.get(key)
            if raw is None:
                continue
            try:
                payload = json.loads(_decode(raw))
            except json.JSONDecodeError:
                continue
            if int(payload.get("admin_user_id", -1)) == admin_user_id:
                self._redis.delete(key)
                deleted += 1
        return deleted

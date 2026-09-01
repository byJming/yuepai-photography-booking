from __future__ import annotations

import base64
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import fakeredis
import pyotp
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from app.core.config import Settings
from app.core.database import Base
from app.core.security import FieldCipher, hash_password
from app.main import create_app
from app.models import AdminUser, AvailabilitySlot, MediaAsset, User
from app.services.sessions import CustomerSessionService


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    settings = Settings(
        _env_file=None,
        app_env="test",
        mysql_dsn="sqlite+pysqlite:///:memory:",
        redis_url="redis://127.0.0.1:6379/2",
        redis_key_prefix="yuepai:api-test",
        wechat_app_id="test-app-id",
        wechat_app_secret="test-app-secret",  # noqa: S106
        field_encryption_key_v1=base64.b64encode(b"k" * 32).decode(),
        openid_hmac_key="h" * 32,
        session_token_pepper="s" * 32,
        admin_session_token_pepper="a" * 32,
        media_root=tmp_path / "media",
        media_public_base_url="https://your-domain.example/media/public",
        admin_cookie_secure=False,
    )
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    app.state.redis = fakeredis.FakeRedis(decode_responses=True)
    return app


@pytest.fixture
def client(api_app: FastAPI):  # type: ignore[no-untyped-def]
    with TestClient(api_app) as test_client:
        yield test_client


def create_admin(app: FastAPI, *, totp_enabled: bool = True) -> str | None:
    settings = app.state.settings
    cipher = FieldCipher(settings.field_encryption_key_v1)
    secret = pyotp.random_base32() if totp_enabled else None
    now = datetime.now(UTC).replace(tzinfo=None)
    with app.state.session_factory() as db:
        db.add(
            AdminUser(
                username="owner",
                password_hash=hash_password("very-strong-password"),
                totp_secret_ciphertext=(
                    cipher.encrypt(secret, "admin_users.totp:owner") if secret else None
                ),
                totp_enabled=totp_enabled,
                status="active",
                failed_login_count=0,
                password_changed_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        db.commit()
    return secret


def login_admin(client: TestClient, secret: str | None) -> tuple[str, str | None]:
    code = pyotp.TOTP(secret).now() if secret else None
    body = {
        "username": "owner",
        "password": "very-strong-password",
    }
    if code:
        body["totp_code"] = code
    response = client.post(
        "/api/admin/v1/auth/login",
        json=body,
    )
    assert response.status_code == 200
    return response.json()["data"]["csrf_token"], code


def create_customer_token(app: FastAPI) -> str:
    now = datetime.now(UTC).replace(tzinfo=None)
    with app.state.session_factory() as db:
        user = User(
            openid_hash=b"u" * 32,
            openid_ciphertext=None,
            status="active",
            last_login_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return CustomerSessionService(
            app.state.redis,
            app.state.settings.redis_key_prefix,
            app.state.settings.session_token_pepper,
            app.state.settings.session_ttl_seconds,
        ).create(user.id)


def test_customer_bearer_token_cannot_access_admin_api(
    api_app: FastAPI, client: TestClient
) -> None:
    token = create_customer_token(api_app)

    response = client.get(
        "/api/admin/v1/dashboard", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_EXPIRED"


def test_admin_cookie_cannot_replace_customer_bearer_token(
    api_app: FastAPI, client: TestClient
) -> None:
    secret = create_admin(api_app)
    login_admin(client, secret)

    response = client.get("/api/v1/bookings")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_EXPIRED"


def test_admin_mutations_require_valid_csrf(api_app: FastAPI, client: TestClient) -> None:
    secret = create_admin(api_app)
    login_admin(client, secret)
    body = {"slug": "summer", "title": "夏日", "category_code": "portrait"}

    missing = client.post("/api/admin/v1/portfolio-series", json=body)
    wrong = client.post(
        "/api/admin/v1/portfolio-series",
        json=body,
        headers={"X-CSRF-Token": "wrong-token"},
    )
    logout_without_csrf = client.post("/api/admin/v1/auth/logout")

    assert missing.status_code == 403
    assert wrong.status_code == 403
    assert logout_without_csrf.status_code == 403
    assert missing.json()["error"]["code"] == "ADMIN_CSRF_FAILED"


def test_admin_session_restore_rotates_csrf(api_app: FastAPI, client: TestClient) -> None:
    secret = create_admin(api_app)
    login_csrf, _ = login_admin(client, secret)

    restored = client.get("/api/admin/v1/auth/me")

    assert restored.status_code == 200
    restored_data = restored.json()["data"]
    restored_csrf = restored_data["csrf_token"]
    assert restored_data["username"] == "owner"
    assert restored_csrf
    assert restored_csrf != login_csrf

    rejected = client.post(
        "/api/admin/v1/portfolio-series",
        json={"slug": "old-token", "title": "旧令牌", "category_code": "portrait"},
        headers={"X-CSRF-Token": login_csrf},
    )
    accepted = client.post(
        "/api/admin/v1/portfolio-series",
        json={"slug": "new-token", "title": "新令牌", "category_code": "portrait"},
        headers={"X-CSRF-Token": restored_csrf},
    )
    logout = client.post(
        "/api/admin/v1/auth/logout",
        headers={"X-CSRF-Token": restored_csrf},
    )

    assert rejected.status_code == 403
    assert rejected.json()["error"]["code"] == "ADMIN_CSRF_FAILED"
    assert accepted.status_code == 201
    assert logout.status_code == 200


def test_admin_responses_are_never_cached(api_app: FastAPI, client: TestClient) -> None:
    secret = create_admin(api_app)
    csrf_token, _ = login_admin(client, secret)

    responses = [
        client.get("/api/admin/v1/dashboard"),
        client.get("/api/admin/v1/settings"),
        client.patch(
            "/api/admin/v1/settings/feature_flags",
            json={
                "value": {
                    "subscription_message": False,
                    "reference_upload": False,
                }
            },
            headers={"X-CSRF-Token": csrf_token},
        ),
    ]

    assert all(response.status_code == 200 for response in responses)
    assert all(response.headers.get("Cache-Control") == "no-store" for response in responses)


def test_password_change_accepts_totp_used_for_current_login(
    api_app: FastAPI, client: TestClient
) -> None:
    secret = create_admin(api_app)
    csrf_token, login_code = login_admin(client, secret)

    response = client.post(
        "/api/admin/v1/auth/change-password",
        json={
            "old_password": "very-strong-password",
            "new_password": "another-strong-password",
            "totp_code": login_code,
        },
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 200
    assert response.json()["data"]["reauthentication_required"] is True
    assert client.get("/api/admin/v1/auth/me").status_code == 401


def test_password_change_without_totp_when_disabled(
    api_app: FastAPI, client: TestClient
) -> None:
    secret = create_admin(api_app, totp_enabled=False)
    csrf_token, _ = login_admin(client, secret)

    response = client.post(
        "/api/admin/v1/auth/change-password",
        json={
            "old_password": "very-strong-password",
            "new_password": "another-strong-password",
        },
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 200
    assert response.json()["data"]["reauthentication_required"] is True
    assert client.get("/api/admin/v1/auth/me").status_code == 401


def test_admin_can_enable_totp_after_password_only_login(
    api_app: FastAPI, client: TestClient
) -> None:
    secret = create_admin(api_app, totp_enabled=False)
    login_admin(client, secret)

    me = client.get("/api/admin/v1/auth/me")
    restored_csrf = me.json()["data"]["csrf_token"]
    setup = client.post(
        "/api/admin/v1/auth/totp/setup",
        headers={"X-CSRF-Token": restored_csrf},
    )

    assert me.status_code == 200
    assert me.json()["data"]["totp_enabled"] is False
    assert setup.status_code == 200
    setup_data = setup.json()["data"]
    assert setup_data["secret"]
    assert setup_data["otpauth_uri"].startswith("otpauth://totp/")

    enable = client.post(
        "/api/admin/v1/auth/totp/enable",
        json={"totp_code": pyotp.TOTP(setup_data["secret"]).now()},
        headers={"X-CSRF-Token": restored_csrf},
    )

    assert enable.status_code == 200
    enable_data = enable.json()["data"]
    assert enable_data["totp_enabled"] is True
    assert enable_data["csrf_token"]
    current_session = client.get("/api/admin/v1/auth/me")
    assert current_session.status_code == 200
    assert current_session.json()["data"]["totp_enabled"] is True
    current_csrf = current_session.json()["data"]["csrf_token"]

    logout = client.post(
        "/api/admin/v1/auth/logout",
        headers={"X-CSRF-Token": current_csrf},
    )
    assert logout.status_code == 200

    missing_code = client.post(
        "/api/admin/v1/auth/login",
        json={"username": "owner", "password": "very-strong-password"},
    )
    assert missing_code.status_code == 401


def test_admin_can_skip_confirmed_slots_and_delete_unconfirmed_slots(
    api_app: FastAPI,
    client: TestClient,
) -> None:
    secret = create_admin(api_app)
    csrf_token, _ = login_admin(client, secret)
    now = datetime.now(UTC).replace(tzinfo=None)
    with api_app.state.session_factory() as db:
        admin = db.scalar(select(AdminUser).where(AdminUser.username == "owner"))
        assert admin is not None
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

    batch = client.put(
        "/api/admin/v1/availability/batch",
        json={
            "month": "2026-08",
            "slots": [
                {
                    "start_at": "2026-08-10T14:30:00+08:00",
                    "end_at": "2026-08-10T17:00:00+08:00",
                    "status": "blocked",
                },
                {
                    "start_at": "2026-08-11T14:30:00+08:00",
                    "end_at": "2026-08-11T17:00:00+08:00",
                    "status": "open",
                },
            ],
        },
        headers={"X-CSRF-Token": csrf_token},
    )

    assert batch.status_code == 200
    batch_data = batch.json()["data"]
    assert batch_data["saved_count"] == 1
    assert batch_data["skipped_confirmed_count"] == 1
    deletable = next(slot for slot in batch_data["slots"] if slot["status"] == "open")

    deleted = client.delete(
        f"/api/admin/v1/availability/{deletable['id']}?version={deletable['version']}",
        headers={"X-CSRF-Token": csrf_token},
    )
    locked = next(slot for slot in batch_data["slots"] if slot["status"] == "confirmed")
    rejected = client.delete(
        f"/api/admin/v1/availability/{locked['id']}?version={locked['version']}",
        headers={"X-CSRF-Token": csrf_token},
    )

    assert deleted.status_code == 200
    assert rejected.status_code == 409
    assert "已确认档期不能删除" in rejected.json()["error"]["message"]


def test_admin_can_upload_sanitized_image(api_app: FastAPI, client: TestClient) -> None:
    secret = create_admin(api_app)
    csrf_token, _ = login_admin(client, secret)
    source = BytesIO()
    Image.new("RGB", (1200, 800), "#c98f7c").save(source, format="JPEG")

    response = client.post(
        "/api/admin/v1/media",
        headers={"X-CSRF-Token": csrf_token},
        files={"file": ("portrait.jpg", source.getvalue(), "image/jpeg")},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["url"].startswith("https://your-domain.example/media/public/")
    assert data["thumbnail_url"].startswith("https://your-domain.example/media/public/")
    with api_app.state.session_factory() as db:
        asset = db.get(MediaAsset, data["id"])
        assert asset is not None
        assert asset.status == "ready"
        assert (
            api_app.state.settings.media_root / "public" / asset.object_key
        ).is_file()
        assert (
            api_app.state.settings.media_root / "public" / asset.thumbnail_object_key
        ).is_file()

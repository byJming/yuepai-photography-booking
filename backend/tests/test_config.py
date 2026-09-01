import base64

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def valid_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "mysql_dsn": "sqlite+pysqlite:///:memory:",
        "redis_url": "redis://127.0.0.1:6379/2",
        "wechat_app_id": "test-app-id",
        "wechat_app_secret": "test-app-secret",
        "field_encryption_key_v1": base64.b64encode(b"k" * 32).decode(),
        "openid_hmac_key": "h" * 32,
        "session_token_pepper": "s" * 32,
        "admin_session_token_pepper": "a" * 32,
        "media_root": "./.test-data/media",
        "admin_cookie_secure": False,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_valid_test_settings() -> None:
    settings = valid_settings()
    assert settings.redis_db == 2
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.admin_api_v1_prefix == "/api/admin/v1"


def test_production_rejects_placeholder_secret() -> None:
    with pytest.raises(ValidationError):
        valid_settings(app_env="production", wechat_app_secret="replace-me")  # noqa: S106


def test_encryption_key_must_be_32_bytes() -> None:
    with pytest.raises(ValidationError):
        valid_settings(field_encryption_key_v1=base64.b64encode(b"short").decode())

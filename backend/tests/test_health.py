import base64

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_liveness_does_not_touch_external_services() -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        mysql_dsn="sqlite+pysqlite:///:memory:",
        redis_url="redis://127.0.0.1:6379/2",
        wechat_app_id="test-app-id",
        wechat_app_secret="test-app-secret",  # noqa: S106
        field_encryption_key_v1=base64.b64encode(b"k" * 32).decode(),
        openid_hmac_key="h" * 32,
        session_token_pepper="s" * 32,
        admin_session_token_pepper="a" * 32,
        media_root="./.test-data/media",
        admin_cookie_secure=False,
    )
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["data"] == {"status": "ok"}
    assert response.headers["X-Request-ID"]

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置；生产环境对密钥和上游凭据进行严格校验。"""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_host: str = "127.0.0.1"
    app_port: int = Field(default=8100, ge=1, le=65535)
    app_log_level: str = "INFO"
    app_public_base_url: str = "https://your-domain.example"
    admin_public_base_url: str = "https://your-domain.example/admin"
    api_v1_prefix: str = "/api/v1"
    admin_api_v1_prefix: str = "/api/admin/v1"

    mysql_dsn: str
    mysql_pool_size: int = Field(default=3, ge=1, le=10)
    mysql_max_overflow: int = Field(default=2, ge=0, le=10)
    mysql_pool_recycle: int = Field(default=1800, ge=60)

    redis_url: str
    redis_key_prefix: str = "yuepai:dev"

    wechat_app_id: str
    wechat_app_secret: str
    wechat_api_base_url: str = "https://api.weixin.qq.com"

    field_encryption_key_v1: str
    openid_hmac_key: str = Field(min_length=32)
    session_token_pepper: str = Field(min_length=32)
    admin_session_token_pepper: str = Field(min_length=32)
    admin_cookie_name: str = "yp_admin_session"

    media_provider: Literal["local"] = "local"
    media_root: Path = Path("./media")
    media_public_base_url: str = "https://your-domain.example/media/public"
    media_max_upload_bytes: int = Field(default=15 * 1024 * 1024, ge=1024)
    media_max_pixels: int = Field(default=20_000_000, ge=1_000_000)
    media_process_concurrency: int = Field(default=1, ge=1, le=2)

    session_ttl_seconds: int = Field(default=604_800, ge=300)
    admin_session_absolute_ttl_seconds: int = Field(default=28_800, ge=900)
    admin_session_idle_ttl_seconds: int = Field(default=1_800, ge=300)
    admin_cookie_secure: bool = True
    cors_allowed_origins: list[str] = Field(default_factory=list)

    @field_validator("field_encryption_key_v1")
    @classmethod
    def validate_encryption_key(cls, value: str) -> str:
        try:
            decoded = base64.b64decode(value, validate=True)
        except ValueError as exc:
            raise ValueError("FIELD_ENCRYPTION_KEY_V1 必须是有效 Base64") from exc
        if len(decoded) != 32:
            raise ValueError("FIELD_ENCRYPTION_KEY_V1 解码后必须为 32 字节")
        return value

    @model_validator(mode="after")
    def validate_production_secrets(self) -> Settings:
        if self.app_env != "production":
            return self
        required = {
            "WECHAT_APP_ID": self.wechat_app_id,
            "WECHAT_APP_SECRET": self.wechat_app_secret,
            "OPENID_HMAC_KEY": self.openid_hmac_key,
            "SESSION_TOKEN_PEPPER": self.session_token_pepper,
            "ADMIN_SESSION_TOKEN_PEPPER": self.admin_session_token_pepper,
        }
        invalid = [name for name, value in required.items() if "replace" in value.lower()]
        if invalid:
            raise ValueError(f"生产配置仍包含占位值：{', '.join(invalid)}")
        if not self.admin_cookie_secure:
            raise ValueError("生产环境必须启用 Secure 管理员 Cookie")
        if not self.app_public_base_url.startswith("https://"):
            raise ValueError("生产公开地址必须使用 HTTPS")
        return self

    @property
    def redis_db(self) -> int:
        path = urlparse(self.redis_url).path.strip("/")
        return int(path or "0")


@lru_cache
def get_settings() -> Settings:
    return Settings()

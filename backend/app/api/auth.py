from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.api.deps import CurrentUser, Db, customer_sessions
from app.core.api import success
from app.core.security import FieldCipher
from app.schemas.auth import WechatLoginRequest
from app.services.auth import CustomerAuthService
from app.services.rate_limit import RateLimiter
from app.services.wechat import WechatClient

router = APIRouter(prefix="/auth", tags=["客户认证"])


@router.post("/wechat-login")
async def wechat_login(body: WechatLoginRequest, request: Request, db: Db) -> dict[str, Any]:
    settings = request.app.state.settings
    client_ip = request.client.host if request.client else "unknown"
    RateLimiter(request.app.state.redis, settings.redis_key_prefix).check(
        "wechat_login", client_ip, 10, 60
    )
    wechat = WechatClient(
        request.app.state.http_client,
        settings.wechat_app_id,
        settings.wechat_app_secret,
        settings.wechat_api_base_url,
    )
    exchanged = await wechat.exchange(body.code)
    auth = CustomerAuthService(
        customer_sessions(request),
        FieldCipher(settings.field_encryption_key_v1),
        settings.openid_hmac_key,
        settings.session_ttl_seconds,
    )
    result = auth.login(db, exchanged.openid)
    return success(
        request,
        {"access_token": result.access_token, "expires_in": result.expires_in},
    )


@router.post("/logout")
def logout(request: Request, user: CurrentUser) -> dict[str, Any]:
    customer_sessions(request).delete(request.state.customer_token)
    return success(request, {})

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.errors import BusinessError, UpstreamServiceError


class InvalidWechatCodeError(BusinessError):
    status_code = 401
    code = "AUTH_INVALID_CODE"
    message = "微信登录凭证无效，请重试。"


@dataclass(frozen=True)
class WechatSession:
    openid: str
    session_key: str


class WechatClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        app_id: str,
        app_secret: str,
        base_url: str,
    ) -> None:
        self._client = client
        self._app_id = app_id
        self._app_secret = app_secret
        self._base_url = base_url.rstrip("/")

    async def exchange(self, code: str) -> WechatSession:
        try:
            response = await self._client.get(
                f"{self._base_url}/sns/jscode2session",
                params={
                    "appid": self._app_id,
                    "secret": self._app_secret,
                    "js_code": code,
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise UpstreamServiceError("微信登录服务暂时不可用，请稍后重试。") from exc
        if payload.get("errcode"):
            if int(payload["errcode"]) in {40029, 40163}:
                raise InvalidWechatCodeError()
            raise UpstreamServiceError("微信登录服务暂时不可用，请稍后重试。")
        openid = payload.get("openid")
        session_key = payload.get("session_key")
        if not isinstance(openid, str) or not isinstance(session_key, str):
            raise UpstreamServiceError("微信登录服务返回了无效响应。")
        return WechatSession(openid=openid, session_key=session_key)

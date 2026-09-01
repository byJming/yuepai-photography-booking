import httpx
import pytest

from app.core.errors import BusinessError, UpstreamServiceError
from app.services.wechat import WechatClient


@pytest.mark.anyio
async def test_code_exchange_success() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["js_code"] == "valid-code"
        return httpx.Response(200, json={"openid": "openid-1", "session_key": "secret"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await WechatClient(
        client, "app-id", "app-secret", "https://api.weixin.qq.com"
    ).exchange("valid-code")
    await client.aclose()

    assert result.openid == "openid-1"
    assert result.session_key == "secret"


@pytest.mark.anyio
async def test_code_exchange_maps_invalid_code() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errcode": 40029, "errmsg": "invalid code"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(BusinessError) as caught:
        await WechatClient(client, "app-id", "app-secret", "https://api.weixin.qq.com").exchange(
            "invalid-code"
        )
    await client.aclose()

    assert caught.value.code == "AUTH_INVALID_CODE"


@pytest.mark.anyio
async def test_code_exchange_maps_network_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(UpstreamServiceError):
        await WechatClient(client, "app-id", "app-secret", "https://api.weixin.qq.com").exchange(
            "any-code"
        )
    await client.aclose()

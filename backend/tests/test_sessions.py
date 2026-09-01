import json

import fakeredis

from app.services.sessions import AdminSessionService, CustomerSessionService


def test_customer_and_admin_sessions_use_separate_namespaces() -> None:
    client = fakeredis.FakeRedis(decode_responses=True)
    customer = CustomerSessionService(client, "yuepai:test", "customer-pepper", 3600)
    admin = AdminSessionService(client, "yuepai:test", "admin-pepper", 3600, 1800)

    customer_token = customer.create(12)
    admin_token, csrf_token = admin.create(7)

    assert customer.get_user_id(customer_token) == 12
    assert admin.get(admin_token).admin_user_id == 7
    assert admin.verify_csrf(admin_token, csrf_token) is True
    keys = {key.decode() if isinstance(key, bytes) else key for key in client.scan_iter("*")}
    assert any(":session:" in key for key in keys)
    assert any(":admin_session:" in key for key in keys)


def test_invalid_session_tokens_return_none() -> None:
    client = fakeredis.FakeRedis(decode_responses=True)
    customer = CustomerSessionService(client, "yuepai:test", "pepper" * 8, 3600)
    admin = AdminSessionService(client, "yuepai:test", "admin" * 8, 3600, 1800)

    assert customer.get_user_id("missing") is None
    assert admin.get("missing") is None
    assert admin.verify_csrf("missing", "missing") is False


def test_admin_session_payload_never_contains_raw_csrf() -> None:
    client = fakeredis.FakeRedis(decode_responses=True)
    admin = AdminSessionService(client, "yuepai:test", "admin" * 8, 3600, 1800)
    token, csrf = admin.create(1)
    stored = next(client.scan_iter("*"))
    payload = json.loads(client.get(stored))

    assert csrf not in json.dumps(payload)
    assert token not in (stored.decode() if isinstance(stored, bytes) else stored)


def test_refreshing_admin_csrf_invalidates_previous_token() -> None:
    client = fakeredis.FakeRedis(decode_responses=True)
    admin = AdminSessionService(client, "yuepai:test", "admin" * 8, 3600, 1800)
    token, csrf = admin.create(1, totp_step=123)
    original_session = admin.get(token)

    refreshed_csrf = admin.refresh_csrf(token)

    assert refreshed_csrf
    assert refreshed_csrf != csrf
    assert admin.verify_csrf(token, csrf) is False
    assert admin.verify_csrf(token, refreshed_csrf) is True
    assert admin.get(token) == original_session


def test_refreshing_csrf_for_missing_admin_session_returns_none() -> None:
    client = fakeredis.FakeRedis(decode_responses=True)
    admin = AdminSessionService(client, "yuepai:test", "admin" * 8, 3600, 1800)

    assert admin.refresh_csrf("missing") is None

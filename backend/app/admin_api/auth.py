from __future__ import annotations

from typing import Any

import pyotp
from fastapi import APIRouter, Request, Response

from app.api.deps import CsrfAdmin, CurrentAdmin, Db, admin_sessions
from app.core.api import success
from app.core.errors import AuthenticationError, ConflictError, DomainValidationError
from app.core.security import FieldCipher, hash_password, verify_password
from app.models import AuditLog
from app.schemas.auth import AdminLoginRequest, ChangePasswordRequest, TotpEnableRequest
from app.services.auth import AdminAuthenticationError, AdminAuthService, verify_admin_totp
from app.services.rate_limit import RateLimiter
from app.utils.time import utc_now

router = APIRouter(prefix="/auth", tags=["管理员认证"])
_TOTP_ISSUER = "摄影预约管理后台"


def _set_admin_cookie(response: Response, request: Request, session_token: str) -> None:
    settings = request.app.state.settings
    response.set_cookie(
        settings.admin_cookie_name,
        session_token,
        max_age=settings.admin_session_absolute_ttl_seconds,
        secure=settings.admin_cookie_secure,
        httponly=True,
        samesite="strict",
        path="/api/admin/",
    )


@router.post("/login")
def login(body: AdminLoginRequest, request: Request, response: Response, db: Db) -> dict[str, Any]:
    settings = request.app.state.settings
    client_ip = request.client.host if request.client else "unknown"
    RateLimiter(request.app.state.redis, settings.redis_key_prefix).check(
        "admin_login", client_ip, 5, 600
    )
    result = AdminAuthService(
        admin_sessions(request), FieldCipher(settings.field_encryption_key_v1)
    ).login(db, body.username, body.password, body.totp_code)
    _set_admin_cookie(response, request, result.session_token)
    return success(
        request,
        {
            "admin": {
                "id": result.admin_user_id,
                "username": result.username,
                "totp_enabled": result.totp_enabled,
            },
            "csrf_token": result.csrf_token,
        },
    )


@router.get("/me")
def me(request: Request, admin: CurrentAdmin) -> dict[str, Any]:
    csrf_token = admin_sessions(request).refresh_csrf(request.state.admin_token)
    if csrf_token is None:
        raise AuthenticationError("管理员登录状态已失效。")
    return success(
        request,
        {
            "id": admin.id,
            "username": admin.username,
            "totp_enabled": admin.totp_enabled,
            "csrf_token": csrf_token,
        },
    )


@router.post("/logout")
def logout(request: Request, response: Response, admin: CsrfAdmin) -> dict[str, Any]:
    settings = request.app.state.settings
    admin_sessions(request).delete(request.state.admin_token)
    response.delete_cookie(settings.admin_cookie_name, path="/api/admin/")
    return success(request, {})


@router.post("/totp/setup")
def setup_totp(request: Request, db: Db, admin: CsrfAdmin) -> dict[str, Any]:
    if admin.totp_enabled:
        raise ConflictError("动态验证码已经启用。")
    settings = request.app.state.settings
    secret = pyotp.random_base32()
    admin.totp_secret_ciphertext = FieldCipher(settings.field_encryption_key_v1).encrypt(
        secret, f"admin_users.totp:{admin.username}"
    )
    admin.updated_at = utc_now()
    db.commit()
    uri = pyotp.TOTP(secret).provisioning_uri(name=admin.username, issuer_name=_TOTP_ISSUER)
    return success(
        request,
        {
            "secret": secret,
            "otpauth_uri": uri,
            "issuer": _TOTP_ISSUER,
            "account_name": admin.username,
        },
    )


@router.post("/totp/enable")
def enable_totp(
    body: TotpEnableRequest,
    request: Request,
    response: Response,
    db: Db,
    admin: CsrfAdmin,
) -> dict[str, Any]:
    if admin.totp_enabled:
        raise ConflictError("动态验证码已经启用。")
    settings = request.app.state.settings
    sessions = admin_sessions(request)
    step = verify_admin_totp(
        admin,
        FieldCipher(settings.field_encryption_key_v1),
        body.totp_code,
    )
    if step is None or not sessions.consume_totp_step(admin.id, step):
        raise DomainValidationError("动态验证码不正确，请等待验证码刷新后重试。")
    admin.totp_enabled = True
    admin.updated_at = utc_now()
    db.add(
        AuditLog(
            actor_admin_user_id=admin.id,
            action="admin.totp.enable",
            entity_type="admin_user",
            entity_id=admin.id,
            request_id=request.state.request_id,
            metadata_json={},
            created_at=utc_now(),
        )
    )
    db.commit()
    sessions.delete_all_for_admin(admin.id)
    session_token, csrf_token = sessions.create(admin.id, totp_step=step)
    _set_admin_cookie(response, request, session_token)
    return success(
        request,
        {"totp_enabled": True, "csrf_token": csrf_token},
    )


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    db: Db,
    admin: CsrfAdmin,
) -> dict[str, Any]:
    settings = request.app.state.settings
    if not verify_password(admin.password_hash, body.old_password):
        raise AdminAuthenticationError()
    sessions = admin_sessions(request)
    if admin.totp_enabled:
        step = verify_admin_totp(
            admin,
            FieldCipher(settings.field_encryption_key_v1),
            body.totp_code,
        )
        if step is None:
            raise AdminAuthenticationError()
        login_totp_step = request.state.admin_session.totp_step
        if step != login_totp_step and not sessions.consume_totp_step(admin.id, step):
            raise AdminAuthenticationError()
    now = utc_now()
    admin.password_hash = hash_password(body.new_password)
    admin.password_changed_at = now
    admin.updated_at = now
    db.commit()
    sessions.delete_all_for_admin(admin.id)
    response.delete_cookie(settings.admin_cookie_name, path="/api/admin/")
    return success(request, {"reauthentication_required": True})

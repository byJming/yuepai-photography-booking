from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import Cookie, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AuthenticationError, AuthorizationError
from app.models import AdminUser, User
from app.services.sessions import AdminSessionService, CustomerSessionService


def get_db(request: Request) -> Generator[Session, None, None]:
    db = request.app.state.session_factory()
    try:
        yield db
    finally:
        db.close()


Db = Annotated[Session, Depends(get_db)]


def customer_sessions(request: Request) -> CustomerSessionService:
    settings = request.app.state.settings
    return CustomerSessionService(
        request.app.state.redis,
        settings.redis_key_prefix,
        settings.session_token_pepper,
        settings.session_ttl_seconds,
    )


def admin_sessions(request: Request) -> AdminSessionService:
    settings = request.app.state.settings
    return AdminSessionService(
        request.app.state.redis,
        settings.redis_key_prefix,
        settings.admin_session_token_pepper,
        settings.admin_session_absolute_ttl_seconds,
        settings.admin_session_idle_ttl_seconds,
    )


def current_user(
    request: Request,
    db: Db,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationError()
    token = authorization[7:].strip()
    user_id = customer_sessions(request).get_user_id(token)
    if user_id is None:
        raise AuthenticationError()
    user = db.scalar(select(User).where(User.id == user_id, User.status == "active"))
    if user is None:
        raise AuthenticationError()
    request.state.user_id = user.id
    request.state.customer_token = token
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def current_admin(
    request: Request,
    db: Db,
    admin_cookie: Annotated[str | None, Cookie(alias="yp_admin_session")] = None,
) -> AdminUser:
    settings = request.app.state.settings
    token = request.cookies.get(settings.admin_cookie_name) or admin_cookie
    if not token:
        raise AuthenticationError("管理员登录状态已失效。")
    session = admin_sessions(request).get(token)
    if session is None:
        raise AuthenticationError("管理员登录状态已失效。")
    admin = db.scalar(
        select(AdminUser).where(AdminUser.id == session.admin_user_id, AdminUser.status == "active")
    )
    if admin is None:
        raise AuthenticationError("管理员登录状态已失效。")
    request.state.admin_user_id = admin.id
    request.state.admin_token = token
    request.state.admin_session = session
    return admin


CurrentAdmin = Annotated[AdminUser, Depends(current_admin)]


def require_csrf(
    request: Request,
    admin: CurrentAdmin,
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> AdminUser:
    csrf_valid = csrf_token and admin_sessions(request).verify_csrf(
        request.state.admin_token, csrf_token
    )
    if not csrf_valid:
        error = AuthorizationError("安全校验失败，请刷新页面后重试。")
        error.code = "ADMIN_CSRF_FAILED"
        raise error
    return admin


CsrfAdmin = Annotated[AdminUser, Depends(require_csrf)]

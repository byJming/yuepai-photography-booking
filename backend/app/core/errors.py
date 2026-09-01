from __future__ import annotations

from typing import Any


class BusinessError(Exception):
    status_code = 400
    code = "BUSINESS_ERROR"
    message = "请求无法处理。"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or self.message)
        self.public_message = message or self.message
        self.details = details or {}


class AuthenticationError(BusinessError):
    status_code = 401
    code = "SESSION_EXPIRED"
    message = "登录状态已失效，请重试。"


class AuthorizationError(BusinessError):
    status_code = 403
    code = "FORBIDDEN"
    message = "你没有权限执行此操作。"


class NotFoundError(BusinessError):
    status_code = 404
    code = "NOT_FOUND"
    message = "请求的数据不存在。"


class ConflictError(BusinessError):
    status_code = 409
    code = "CONFLICT"
    message = "数据状态已发生变化，请刷新后重试。"


class DomainValidationError(BusinessError):
    status_code = 422
    code = "VALIDATION_FAILED"
    message = "请检查填写内容。"


class UpstreamServiceError(BusinessError):
    status_code = 502
    code = "UPSTREAM_UNAVAILABLE"
    message = "外部服务暂时不可用，请稍后重试。"

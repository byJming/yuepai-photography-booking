from __future__ import annotations

from typing import Any

from fastapi import Request


def success(request: Request, data: Any) -> dict[str, Any]:
    return {"data": data, "request_id": request.state.request_id}

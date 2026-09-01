from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Header, Query, Request

from app.api.deps import CurrentUser, Db
from app.core.api import success
from app.core.security import FieldCipher
from app.schemas.booking import BookingCancelRequest, BookingCreateRequest, BookingUpdateRequest
from app.services.booking_views import BookingViewService
from app.services.bookings import BookingService
from app.services.rate_limit import RateLimiter

router = APIRouter(tags=["客户预约"])


def _services(request: Request) -> tuple[BookingService, BookingViewService]:
    cipher = FieldCipher(request.app.state.settings.field_encryption_key_v1)
    return BookingService(cipher), BookingViewService(cipher)


@router.post("/bookings", status_code=201)
def create_booking(
    body: BookingCreateRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
) -> dict[str, Any]:
    limiter = RateLimiter(request.app.state.redis, request.app.state.settings.redis_key_prefix)
    limiter.check("booking_create_user", str(user.id), 3, 3600)
    limiter.check(
        "booking_create_ip", request.client.host if request.client else "unknown", 10, 86_400
    )
    service, views = _services(request)
    booking = service.create(db, user.id, idempotency_key, body)
    return success(request, views.customer_detail(db, booking))


@router.get("/bookings")
def list_bookings(
    request: Request,
    db: Db,
    user: CurrentUser,
    limit: int = Query(default=10, ge=1, le=20),
) -> dict[str, Any]:
    service, views = _services(request)
    items = [views.summary(db, item) for item in service.list_for_customer(db, user.id, limit)]
    return success(request, {"items": items, "next_cursor": None})


@router.get("/bookings/{booking_no}")
def booking_detail(booking_no: str, request: Request, db: Db, user: CurrentUser) -> dict[str, Any]:
    service, views = _services(request)
    booking = service.get_for_customer(db, user.id, booking_no)
    return success(request, views.customer_detail(db, booking))


@router.patch("/bookings/{booking_no}")
def update_booking(
    booking_no: str,
    body: BookingUpdateRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
) -> dict[str, Any]:
    service, views = _services(request)
    booking = service.update(db, user.id, booking_no, body)
    return success(request, views.customer_detail(db, booking))


@router.post("/bookings/{booking_no}/cancel")
def cancel_booking(
    booking_no: str,
    body: BookingCancelRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
) -> dict[str, Any]:
    service, views = _services(request)
    booking = service.cancel(db, user.id, booking_no, body)
    return success(request, views.customer_detail(db, booking))


@router.post("/me/data-deletion-requests", status_code=201)
def request_data_deletion(request: Request, db: Db, user: CurrentUser) -> dict[str, Any]:
    service, _ = _services(request)
    deletion = service.request_data_deletion(db, user.id)
    return success(
        request,
        {
            "id": deletion.id,
            "status": deletion.status,
            "created_at": deletion.created_at.isoformat() + "Z",
        },
    )

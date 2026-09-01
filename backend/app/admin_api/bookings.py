from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Query, Request, Response

from app.api.deps import CsrfAdmin, CurrentAdmin, Db
from app.core.api import success
from app.core.security import FieldCipher
from app.schemas.admin import DataDeletionActionRequest
from app.schemas.booking import AdminBookingActionRequest, AvailabilityBatchRequest
from app.services.admin_bookings import AdminBookingService
from app.services.availability import AvailabilityService
from app.services.booking_views import BookingViewService
from app.services.bookings import BookingService
from app.services.data_retention import DataRetentionService

router = APIRouter(tags=["后台预约和档期"])


def _cipher(request: Request) -> FieldCipher:
    return FieldCipher(request.app.state.settings.field_encryption_key_v1)


@router.get("/dashboard")
def dashboard(request: Request, db: Db, admin: CurrentAdmin) -> dict[str, Any]:
    return success(request, AdminBookingService(_cipher(request)).dashboard(db))


@router.get("/bookings")
def list_bookings(
    request: Request,
    db: Db,
    admin: CurrentAdmin,
    status: str | None = Query(default=None, max_length=32),
    date_from: date | None = None,
    date_to: date | None = None,
    phone_last4: str | None = Query(default=None, pattern=r"^\d{4}$"),
    booking_no: str | None = Query(default=None, max_length=20),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> dict[str, Any]:
    data = AdminBookingService(_cipher(request)).list_bookings(
        db,
        status=status,
        date_from=date_from,
        date_to=date_to,
        phone_last4=phone_last4,
        booking_no=booking_no,
        page=page,
        page_size=page_size,
    )
    return success(request, data)


@router.get("/bookings/{booking_no}")
def booking_detail(
    booking_no: str,
    request: Request,
    response: Response,
    db: Db,
    admin: CurrentAdmin,
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    data = AdminBookingService(_cipher(request)).detail(
        db, admin.id, booking_no, request.state.request_id
    )
    return success(request, data)


@router.post("/bookings/{booking_no}/actions")
def booking_action(
    booking_no: str,
    body: AdminBookingActionRequest,
    request: Request,
    db: Db,
    admin: CsrfAdmin,
) -> dict[str, Any]:
    cipher = _cipher(request)
    booking = BookingService(cipher).admin_action(
        db, admin.id, booking_no, body, request.state.request_id
    )
    return success(request, BookingViewService(cipher).customer_detail(db, booking))


@router.get("/availability")
def availability(
    month: str,
    request: Request,
    response: Response,
    db: Db,
    admin: CurrentAdmin,
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return success(
        request,
        {"month": month, "slots": AvailabilityService(_cipher(request)).list_month(db, month)},
    )


@router.put("/availability/batch")
def availability_batch(
    body: AvailabilityBatchRequest,
    request: Request,
    db: Db,
    admin: CsrfAdmin,
) -> dict[str, Any]:
    result = AvailabilityService(_cipher(request)).batch_upsert(
        db, admin.id, body, request.state.request_id
    )
    return success(request, {"month": body.month, **result})


@router.delete("/availability/{slot_id}")
def delete_availability(
    slot_id: int,
    request: Request,
    db: Db,
    admin: CsrfAdmin,
    version: int = Query(ge=1),
) -> dict[str, Any]:
    AvailabilityService(_cipher(request)).delete_slot(
        db,
        admin.id,
        slot_id,
        version,
        request.state.request_id,
    )
    return success(request, {"deleted_id": slot_id})


@router.get("/data-deletion-requests")
def data_deletion_requests(
    request: Request,
    db: Db,
    admin: CurrentAdmin,
    status: str | None = Query(default=None, pattern=r"^(pending|completed|rejected)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> dict[str, Any]:
    data = DataRetentionService(_cipher(request)).list_deletion_requests(
        db, status=status, page=page, page_size=page_size
    )
    return success(request, data)


@router.post("/data-deletion-requests/{deletion_request_id}/actions")
def data_deletion_action(
    deletion_request_id: int,
    body: DataDeletionActionRequest,
    request: Request,
    db: Db,
    admin: CsrfAdmin,
) -> dict[str, Any]:
    service = DataRetentionService(_cipher(request))
    if body.action == "complete":
        deletion = service.complete_deletion_request(
            db, deletion_request_id, admin.id, request.state.request_id
        )
    else:
        deletion = service.reject_deletion_request(
            db, deletion_request_id, admin.id, request.state.request_id
        )
    processed_at = deletion.processed_at
    if processed_at is None:
        raise RuntimeError("数据删除申请处理完成后缺少处理时间。")
    return success(
        request,
        {
            "id": deletion.id,
            "status": deletion.status,
            "processed_at": processed_at.isoformat() + "Z",
        },
    )

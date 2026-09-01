from __future__ import annotations

from enum import StrEnum


class BookingStatus(StrEnum):
    SUBMITTED = "submitted"
    NEEDS_INFO = "needs_info"
    RESCHEDULE_PROPOSED = "reschedule_proposed"
    CONFIRMED = "confirmed"
    DECLINED = "declined"
    CANCELLED_BY_USER = "cancelled_by_user"
    CANCELLED_BY_ADMIN = "cancelled_by_admin"
    COMPLETED = "completed"


class BookingAction(StrEnum):
    CUSTOMER_UPDATE = "customer_update"
    CUSTOMER_CANCEL = "customer_cancel"
    REQUEST_INFO = "request_info"
    PROPOSE_RESCHEDULE = "propose_reschedule"
    CONFIRM = "confirm"
    DECLINE = "decline"
    COMPLETE = "complete"
    ADMIN_CANCEL = "admin_cancel"


_TRANSITIONS: dict[tuple[BookingStatus, BookingAction], BookingStatus] = {
    (BookingStatus.SUBMITTED, BookingAction.REQUEST_INFO): BookingStatus.NEEDS_INFO,
    (
        BookingStatus.SUBMITTED,
        BookingAction.PROPOSE_RESCHEDULE,
    ): BookingStatus.RESCHEDULE_PROPOSED,
    (BookingStatus.SUBMITTED, BookingAction.CONFIRM): BookingStatus.CONFIRMED,
    (BookingStatus.SUBMITTED, BookingAction.DECLINE): BookingStatus.DECLINED,
    (BookingStatus.SUBMITTED, BookingAction.CUSTOMER_CANCEL): BookingStatus.CANCELLED_BY_USER,
    (BookingStatus.NEEDS_INFO, BookingAction.CUSTOMER_UPDATE): BookingStatus.SUBMITTED,
    (
        BookingStatus.NEEDS_INFO,
        BookingAction.CUSTOMER_CANCEL,
    ): BookingStatus.CANCELLED_BY_USER,
    (
        BookingStatus.RESCHEDULE_PROPOSED,
        BookingAction.CUSTOMER_UPDATE,
    ): BookingStatus.SUBMITTED,
    (
        BookingStatus.RESCHEDULE_PROPOSED,
        BookingAction.CUSTOMER_CANCEL,
    ): BookingStatus.CANCELLED_BY_USER,
    (BookingStatus.CONFIRMED, BookingAction.COMPLETE): BookingStatus.COMPLETED,
    (BookingStatus.CONFIRMED, BookingAction.ADMIN_CANCEL): BookingStatus.CANCELLED_BY_ADMIN,
}


def next_status(current: BookingStatus, action: BookingAction) -> BookingStatus:
    """返回动作对应的新状态；未列入状态机的转换一律拒绝。"""

    try:
        return _TRANSITIONS[(current, action)]
    except KeyError as exc:
        raise ValueError(f"当前状态 {current} 不允许动作 {action}") from exc

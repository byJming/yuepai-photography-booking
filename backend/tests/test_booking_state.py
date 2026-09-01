import pytest
from pydantic import ValidationError

from app.schemas.booking import AdminBookingActionRequest
from app.services.booking_state import BookingAction, BookingStatus, next_status


@pytest.mark.parametrize(
    ("current", "action", "expected"),
    [
        (BookingStatus.SUBMITTED, BookingAction.REQUEST_INFO, BookingStatus.NEEDS_INFO),
        (BookingStatus.SUBMITTED, BookingAction.CONFIRM, BookingStatus.CONFIRMED),
        (BookingStatus.NEEDS_INFO, BookingAction.CUSTOMER_UPDATE, BookingStatus.SUBMITTED),
        (
            BookingStatus.RESCHEDULE_PROPOSED,
            BookingAction.CUSTOMER_UPDATE,
            BookingStatus.SUBMITTED,
        ),
        (BookingStatus.CONFIRMED, BookingAction.COMPLETE, BookingStatus.COMPLETED),
    ],
)
def test_legal_transitions(
    current: BookingStatus, action: BookingAction, expected: BookingStatus
) -> None:
    assert next_status(current, action) is expected


def test_illegal_transition_is_rejected() -> None:
    with pytest.raises(ValueError):
        next_status(BookingStatus.COMPLETED, BookingAction.CONFIRM)
@pytest.mark.parametrize("action", ["request_info", "propose_reschedule", "decline", "cancel"])
def test_customer_facing_admin_actions_require_a_message(action: str) -> None:
    with pytest.raises(ValidationError, match="客户可见说明"):
        AdminBookingActionRequest(action=action, version=1, public_message="   ")


def test_admin_action_rejects_unrelated_slot_and_reopen_fields() -> None:
    with pytest.raises(ValidationError, match="只有确认预约"):
        AdminBookingActionRequest(
            action="complete", version=1, slot_id=1, public_message="已完成"
        )
    with pytest.raises(ValidationError, match="只有取消预约"):
        AdminBookingActionRequest(
            action="confirm", version=1, slot_id=1, reopen_slot=True, public_message="已确认"
        )

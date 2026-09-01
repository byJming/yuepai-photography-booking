from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class BookingLocationRequest(BaseModel):
    type: Literal["preset", "custom"]
    code: str | None = Field(default=None, max_length=32)
    text: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_location(self) -> BookingLocationRequest:
        if self.type == "preset" and not self.code:
            raise ValueError("请选择预设地点")
        if self.type == "custom" and not (self.text and self.text.strip()):
            raise ValueError("请填写意向地点")
        return self


class BookingContactRequest(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    phone: str = Field(pattern=r"^1\d{10}$")

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("联系人不能为空")
        return stripped


class BookingCreateRequest(BaseModel):
    requested_date: date
    requested_period_code: Literal["morning", "afternoon", "sunset"]
    participant_count: int = Field(ge=1, le=10)
    budget_code: str | None = Field(default=None, max_length=32)
    location: BookingLocationRequest
    selections: dict[str, list[str]]
    contact: BookingContactRequest
    remark: str = Field(default="", max_length=500)
    privacy_policy_version: str = Field(min_length=1, max_length=32)
    service_terms_version: str = Field(min_length=1, max_length=32)


class BookingUpdateRequest(BaseModel):
    version: int = Field(ge=1)
    requested_date: date | None = None
    requested_period_code: Literal["morning", "afternoon", "sunset"] | None = None
    participant_count: int | None = Field(default=None, ge=1, le=10)
    budget_code: str | None = Field(default=None, max_length=32)
    location: BookingLocationRequest | None = None
    selections: dict[str, list[str]] | None = None
    contact: BookingContactRequest | None = None
    remark: str | None = Field(default=None, max_length=500)


class BookingCancelRequest(BaseModel):
    version: int = Field(ge=1)


class AdminBookingActionRequest(BaseModel):
    action: Literal[
        "request_info",
        "propose_reschedule",
        "confirm",
        "decline",
        "complete",
        "cancel",
    ]
    version: int = Field(ge=1)
    slot_id: int | None = Field(default=None, ge=1)
    public_message: str = Field(default="", max_length=300)
    internal_note: str = Field(default="", max_length=500)
    reopen_slot: bool = False

    @model_validator(mode="after")
    def validate_action(self) -> AdminBookingActionRequest:
        self.public_message = self.public_message.strip()
        self.internal_note = self.internal_note.strip()
        if self.action == "confirm" and self.slot_id is None:
            raise ValueError("确认预约时必须选择档期")
        if self.action != "confirm" and self.slot_id is not None:
            raise ValueError("只有确认预约时可以提交档期")
        if self.action != "cancel" and self.reopen_slot:
            raise ValueError("只有取消预约时可以重新开放档期")
        if (
            self.action in {"request_info", "propose_reschedule", "decline", "cancel"}
            and not self.public_message
        ):
            raise ValueError("该操作必须填写客户可见说明")
        return self


class AvailabilitySlotInput(BaseModel):
    start_at: datetime
    end_at: datetime
    status: Literal["open", "blocked"] = "open"
    public_note: str | None = Field(default=None, max_length=100)
    internal_note: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def validate_range(self) -> AvailabilitySlotInput:
        if self.end_at <= self.start_at:
            raise ValueError("结束时间必须晚于开始时间")
        return self


class AvailabilityBatchRequest(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    slots: list[AvailabilitySlotInput] = Field(max_length=200)

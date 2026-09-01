from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class PortfolioCreateRequest(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=64)
    title: str = Field(min_length=1, max_length=80)
    subtitle: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    category_code: str = Field(min_length=1, max_length=32)
    style_tags: list[str] = Field(default_factory=list, max_length=10)
    location_text: str | None = Field(default=None, max_length=100)
    shot_on: date | None = None
    cover_media_id: int | None = Field(default=None, ge=1)
    sort_order: int = Field(default=0, ge=-10000, le=10000)


class PortfolioUpdateRequest(BaseModel):
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=64)
    title: str | None = Field(default=None, min_length=1, max_length=80)
    subtitle: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    category_code: str | None = Field(default=None, min_length=1, max_length=32)
    style_tags: list[str] | None = Field(default=None, max_length=10)
    location_text: str | None = Field(default=None, max_length=100)
    shot_on: date | None = None
    cover_media_id: int | None = Field(default=None, ge=1)
    sort_order: int | None = Field(default=None, ge=-10000, le=10000)


class PortfolioMediaItem(BaseModel):
    media_id: int = Field(ge=1)
    caption: str | None = Field(default=None, max_length=200)


class PortfolioMediaOrderRequest(BaseModel):
    items: list[PortfolioMediaItem] = Field(max_length=100)

    @model_validator(mode="after")
    def unique_media(self) -> PortfolioMediaOrderRequest:
        ids = [item.media_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("图片不能重复")
        return self


class OptionGroupRequest(BaseModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=32)
    name: str = Field(min_length=1, max_length=40)
    selection_mode: Literal["single", "multiple"]
    is_required: bool = False
    min_select: int = Field(default=0, ge=0, le=20)
    max_select: int = Field(default=1, ge=1, le=20)
    status: Literal["active", "disabled"] = "active"
    sort_order: int = Field(default=0, ge=-10000, le=10000)

    @model_validator(mode="after")
    def selection_limits(self) -> OptionGroupRequest:
        if self.min_select > self.max_select:
            raise ValueError("最少选择数不能大于最多选择数")
        if self.selection_mode == "single" and self.max_select != 1:
            raise ValueError("单选组最多只能选择 1 项")
        return self


class OptionGroupUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    selection_mode: Literal["single", "multiple"] | None = None
    is_required: bool | None = None
    min_select: int | None = Field(default=None, ge=0, le=20)
    max_select: int | None = Field(default=None, ge=1, le=20)
    status: Literal["active", "disabled"] | None = None
    sort_order: int | None = Field(default=None, ge=-10000, le=10000)


class OptionItemRequest(BaseModel):
    group_id: int = Field(ge=1)
    code: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]*$", max_length=32)
    name: str = Field(min_length=1, max_length=60)
    description: str | None = Field(default=None, max_length=300)
    reference_media_id: int | None = Field(default=None, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: Literal["active", "disabled"] = "active"
    sort_order: int = Field(default=0, ge=-10000, le=10000)


class OptionItemUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    description: str | None = Field(default=None, max_length=300)
    reference_media_id: int | None = Field(default=None, ge=1)
    metadata: dict[str, Any] | None = None
    status: Literal["active", "disabled"] | None = None
    sort_order: int | None = Field(default=None, ge=-10000, le=10000)


class BrandSettingValue(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    eyebrow: str = Field(min_length=1, max_length=80)
    monthly_title: str = Field(min_length=1, max_length=80)
    monthly_subtitle: str = Field(min_length=1, max_length=200)
    availability_text: str = Field(min_length=1, max_length=40)
    service_area: str = Field(min_length=1, max_length=100)
    about_text: str = Field(default="", max_length=2000)


class FeatureFlagsSettingValue(BaseModel):
    subscription_message: bool = False
    reference_upload: bool = False


class PolicyVersionsSettingValue(BaseModel):
    privacy: str = Field(pattern=r"^[A-Za-z0-9._-]{1,32}$")
    service_terms: str = Field(pattern=r"^[A-Za-z0-9._-]{1,32}$")


class PolicyContentSettingValue(BaseModel):
    service_scope: str = Field(min_length=1, max_length=5000)
    schedule_and_pricing: str = Field(min_length=1, max_length=5000)
    safety_and_reschedule: str = Field(min_length=1, max_length=5000)
    privacy_and_display: str = Field(min_length=1, max_length=5000)
    cancellation_rules: str = Field(min_length=1, max_length=5000)


class BookingRulesSettingValue(BaseModel):
    open_months: int = Field(ge=1, le=12)
    confirmed_customer_cancel: Literal[False] = False
    data_retention_completed_months: int = Field(ge=1, le=120)
    data_retention_cancelled_months: int = Field(ge=1, le=120)


SETTING_VALUE_MODELS: dict[str, type[BaseModel]] = {
    "brand": BrandSettingValue,
    "feature_flags": FeatureFlagsSettingValue,
    "policy_versions": PolicyVersionsSettingValue,
    "policy_content": PolicyContentSettingValue,
    "booking_rules": BookingRulesSettingValue,
}


def normalize_setting_value(key: str, value: dict[str, Any]) -> dict[str, Any]:
    model = SETTING_VALUE_MODELS.get(key)
    if model is None:
        raise KeyError(key)
    return model.model_validate(value).model_dump()

class SettingsPatchRequest(BaseModel):
    value: dict[str, Any]


class DataDeletionActionRequest(BaseModel):
    action: Literal["complete", "reject"]

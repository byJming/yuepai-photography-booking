from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

PK_TYPE = BigInteger().with_variant(Integer, "sqlite")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_status_login", "status", "last_login_at"),)

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    openid_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False, unique=True)
    openid_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary(255))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)


class AdminUser(TimestampMixin, Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    totp_secret_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary(512))
    totp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    failed_login_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    password_changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class MediaAsset(TimestampMixin, Base):
    __tablename__ = "media_assets"
    __table_args__ = (
        UniqueConstraint("storage_provider", "object_key", name="uq_media_provider_key"),
        Index("ix_media_kind_status", "kind", "status"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    storage_provider: Mapped[str] = mapped_column(String(16), nullable=False, default="local")
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    thumbnail_object_key: Mapped[str | None] = mapped_column(String(512))
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, default="public")
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ready")
    created_by_admin_id: Mapped[int] = mapped_column(
        ForeignKey("admin_users.id", ondelete="RESTRICT"), nullable=False
    )


class PortfolioSeries(TimestampMixin, Base):
    __tablename__ = "portfolio_series"
    __table_args__ = (
        Index("ix_portfolio_status_sort", "status", "sort_order", "published_at"),
        Index("ix_portfolio_category_status", "category_code", "status"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    category_code: Mapped[str] = mapped_column(String(32), nullable=False)
    style_tags_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    location_text: Mapped[str | None] = mapped_column(String(100))
    shot_on: Mapped[date | None] = mapped_column(Date)
    cover_media_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by_admin_id: Mapped[int] = mapped_column(
        ForeignKey("admin_users.id", ondelete="RESTRICT"), nullable=False
    )


class PortfolioSeriesMedia(Base):
    __tablename__ = "portfolio_series_media"
    __table_args__ = (
        UniqueConstraint("series_id", "media_id", name="uq_series_media"),
        UniqueConstraint("series_id", "sort_order", name="uq_series_sort"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    series_id: Mapped[int] = mapped_column(
        ForeignKey("portfolio_series.id", ondelete="CASCADE"), nullable=False
    )
    media_id: Mapped[int] = mapped_column(
        ForeignKey("media_assets.id", ondelete="RESTRICT"), nullable=False
    )
    caption: Mapped[str | None] = mapped_column(String(200))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class BookingOptionGroup(TimestampMixin, Base):
    __tablename__ = "booking_option_groups"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    selection_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    is_required: Mapped[bool] = mapped_column(nullable=False, default=False)
    min_select: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    max_select: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class BookingOptionItem(TimestampMixin, Base):
    __tablename__ = "booking_option_items"
    __table_args__ = (
        UniqueConstraint("group_id", "code", name="uq_option_group_item_code"),
        Index("ix_option_group_status_sort", "group_id", "status", "sort_order"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("booking_option_groups.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    description: Mapped[str | None] = mapped_column(String(300))
    reference_media_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="SET NULL")
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class AvailabilitySlot(TimestampMixin, Base):
    __tablename__ = "availability_slots"
    __table_args__ = (
        UniqueConstraint("start_at", "end_at", name="uq_slot_times"),
        Index("ix_slot_status_start", "status", "start_at"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    public_note: Mapped[str | None] = mapped_column(String(100))
    internal_note_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary(1024))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by_admin_id: Mapped[int] = mapped_column(
        ForeignKey("admin_users.id", ondelete="RESTRICT"), nullable=False
    )


class Booking(TimestampMixin, Base):
    __tablename__ = "bookings"
    __table_args__ = (
        UniqueConstraint("slot_id", name="uq_booking_slot"),
        UniqueConstraint("user_id", "idempotency_key_hash", name="uq_booking_idempotency"),
        Index("ix_booking_user_updated", "user_id", "updated_at"),
        Index("ix_booking_status_date", "status", "requested_date"),
        Index("ix_booking_phone_created", "contact_phone_last4", "created_at"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    booking_no: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    request_fingerprint: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="submitted")
    requested_date: Mapped[date] = mapped_column(Date, nullable=False)
    requested_period_code: Mapped[str] = mapped_column(String(32), nullable=False)
    slot_id: Mapped[int | None] = mapped_column(
        ForeignKey("availability_slots.id", ondelete="RESTRICT")
    )
    participant_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    budget_code: Mapped[str | None] = mapped_column(String(32))
    location_type: Mapped[str] = mapped_column(String(16), nullable=False)
    location_code: Mapped[str | None] = mapped_column(String(32))
    custom_location_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary(1024))
    contact_name_ciphertext: Mapped[bytes] = mapped_column(LargeBinary(512), nullable=False)
    contact_phone_ciphertext: Mapped[bytes] = mapped_column(LargeBinary(512), nullable=False)
    contact_phone_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    remark_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary(2048))
    privacy_policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    service_terms_version: Mapped[str] = mapped_column(String(32), nullable=False)
    consented_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    sensitive_data_cleared_at: Mapped[datetime | None] = mapped_column(DateTime)


class BookingOptionSelection(Base):
    __tablename__ = "booking_option_selections"
    __table_args__ = (
        UniqueConstraint(
            "booking_id", "group_code_snapshot", "item_code_snapshot", name="uq_booking_selection"
        ),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    option_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("booking_option_items.id", ondelete="SET NULL")
    )
    group_code_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    item_code_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    item_name_snapshot: Mapped[str] = mapped_column(String(60), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class BookingEvent(Base):
    __tablename__ = "booking_events"
    __table_args__ = (Index("ix_booking_event_created", "booking_id", "created_at"),)

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_admin_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="SET NULL")
    )
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str | None] = mapped_column(String(32))
    public_message: Mapped[str | None] = mapped_column(String(300))
    internal_note_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary(2048))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AppSetting(Base):
    __tablename__ = "app_settings"

    setting_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_json: Mapped[Any] = mapped_column(JSON, nullable=False)
    is_public: Mapped[bool] = mapped_column(nullable=False, default=False)
    updated_by_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_actor_created", "actor_admin_user_id", "created_at"),
        Index("ix_audit_entity_created", "entity_type", "entity_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    actor_admin_user_id: Mapped[int] = mapped_column(
        ForeignKey("admin_users.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(BigInteger)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class DataDeletionRequest(TimestampMixin, Base):
    __tablename__ = "data_deletion_requests"
    __table_args__ = (Index("ix_deletion_status_created", "status", "created_at"),)

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    processed_by_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="SET NULL")
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)


ALL_MODELS = (
    User,
    AdminUser,
    MediaAsset,
    PortfolioSeries,
    PortfolioSeriesMedia,
    BookingOptionGroup,
    BookingOptionItem,
    AvailabilitySlot,
    Booking,
    BookingOptionSelection,
    BookingEvent,
    AppSetting,
    AuditLog,
    DataDeletionRequest,
)

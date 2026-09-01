from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.errors import DomainValidationError
from app.models import AdminUser, AppSetting, AvailabilitySlot, MediaAsset, PortfolioSeries
from app.services.public import PublicContentService


def build_portfolio_db() -> tuple[Session, AdminUser, MediaAsset, datetime]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    now = datetime.now(UTC).replace(tzinfo=None)
    admin = AdminUser(
        username="owner",
        password_hash="hash",  # noqa: S106
        totp_secret_ciphertext=b"cipher",
        status="active",
        failed_login_count=0,
        password_changed_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(admin)
    db.flush()
    media = MediaAsset(
        storage_provider="local",
        object_key="portfolio/a.jpg",
        thumbnail_object_key="portfolio/a-thumb.jpg",
        visibility="public",
        kind="portfolio_image",
        mime_type="image/jpeg",
        file_size=100,
        width=100,
        height=100,
        sha256="a" * 64,
        status="ready",
        created_by_admin_id=admin.id,
        created_at=now,
        updated_at=now,
    )
    db.add(media)
    db.flush()
    return db, admin, media, now


def make_series(
    admin: AdminUser,
    media: MediaAsset,
    now: datetime,
    slug: str,
    sort_order: int,
    status: str = "published",
) -> PortfolioSeries:
    return PortfolioSeries(
        slug=slug,
        title=slug,
        category_code="portrait",
        style_tags_json=[],
        cover_media_id=media.id,
        status=status,
        sort_order=sort_order,
        published_at=now if status == "published" else None,
        created_by_admin_id=admin.id,
        created_at=now,
        updated_at=now,
    )


def test_public_portfolios_exclude_drafts() -> None:
    db, admin, media, now = build_portfolio_db()
    db.add_all(
        [
            make_series(admin, media, now, "published", 1),
            make_series(admin, media, now, "draft", 2, "draft"),
        ]
    )
    db.commit()

    items, next_cursor = PublicContentService(
        "https://example.com/media/public"
    ).list_portfolios(db, None, 10)

    assert [item["slug"] for item in items] == ["published"]
    assert next_cursor is None
    assert "draft" not in str(items)


def test_portfolio_cursor_preserves_sort_order_without_skipping_items() -> None:
    db, admin, media, now = build_portfolio_db()
    db.add_all(
        [
            make_series(admin, media, now, "first-created", 0),
            make_series(admin, media, now, "second-created", 0),
            make_series(admin, media, now, "third", 1),
            make_series(admin, media, now, "fourth", 2),
        ]
    )
    db.commit()
    service = PublicContentService("https://example.com/media/public")

    first_page, cursor = service.list_portfolios(db, None, 2)
    second_page, next_cursor = service.list_portfolios(db, None, 2, cursor)

    assert [item["slug"] for item in first_page] == ["second-created", "first-created"]
    assert [item["slug"] for item in second_page] == ["third", "fourth"]
    assert cursor == "0:1"
    assert next_cursor is None


def test_portfolio_cursor_rejects_invalid_values() -> None:
    db, _, _, _ = build_portfolio_db()

    with pytest.raises(DomainValidationError, match="作品分页游标无效"):
        PublicContentService("https://example.com/media/public").list_portfolios(
            db, None, 10, "invalid"
        )


def test_bootstrap_returns_public_policy_content() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    now = datetime.now(UTC).replace(tzinfo=None)
    db.add(
        AppSetting(
            setting_key="policy_content",
            value_json={"privacy_and_display": "只用于预约沟通。"},
            is_public=True,
            updated_at=now,
        )
    )
    db.commit()

    result = PublicContentService("https://example.com/media/public").bootstrap(db)

    assert result["policy_content"]["privacy_and_display"] == "只用于预约沟通。"
    assert result["booking_horizon_months"] == 12


def test_bootstrap_reports_nearest_open_availability(monkeypatch: pytest.MonkeyPatch) -> None:
    db, admin, _, now = build_portfolio_db()
    monkeypatch.setattr("app.services.public.local_today", lambda: date(2026, 7, 27))
    monkeypatch.setattr("app.services.public.utc_now", lambda: datetime(2026, 7, 27, 11, 0))
    db.add_all(
        [
            AvailabilitySlot(
                start_at=datetime(2026, 7, 26, 6, 30),
                end_at=datetime(2026, 7, 26, 9, 0),
                status="open",
                version=1,
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            ),
            AvailabilitySlot(
                start_at=datetime(2026, 7, 29, 6, 30),
                end_at=datetime(2026, 7, 29, 9, 0),
                status="closed",
                version=1,
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            ),
            AvailabilitySlot(
                start_at=datetime(2026, 8, 10, 6, 30),
                end_at=datetime(2026, 8, 10, 9, 0),
                status="open",
                version=1,
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            ),
        ]
    )
    db.commit()

    result = PublicContentService("https://example.com/media/public").bootstrap(db)

    assert result["availability_status"] == {
        "available": True,
        "text": "8月10日可约",
        "next_date": "2026-08-10",
    }


def test_bootstrap_reports_when_no_availability_is_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, _, _, _ = build_portfolio_db()
    monkeypatch.setattr("app.services.public.local_today", lambda: date(2026, 7, 27))
    monkeypatch.setattr("app.services.public.utc_now", lambda: datetime(2026, 7, 27, 11, 0))

    result = PublicContentService("https://example.com/media/public").bootstrap(db)

    assert result["availability_status"] == {
        "available": False,
        "text": "暂无开放档期",
        "next_date": None,
    }

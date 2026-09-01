from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import AdminUser, MediaAsset, PortfolioSeries, PortfolioSeriesMedia
from app.services.admin_content import AdminContentService


def test_portfolio_detail_returns_ordered_media() -> None:
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
    media = []
    for index in range(2):
        item = MediaAsset(
            storage_provider="local",
            object_key=f"portfolio/{index}.jpg",
            thumbnail_object_key=f"portfolio/{index}-thumb.jpg",
            visibility="public",
            kind="portfolio_image",
            mime_type="image/jpeg",
            file_size=100,
            width=800,
            height=1200,
            sha256=str(index) * 64,
            status="ready",
            created_by_admin_id=admin.id,
            created_at=now,
            updated_at=now,
        )
        db.add(item)
        media.append(item)
    db.flush()
    series = PortfolioSeries(
        slug="summer",
        title="夏日",
        category_code="portrait",
        style_tags_json=["自然"],
        cover_media_id=media[0].id,
        status="draft",
        sort_order=0,
        created_by_admin_id=admin.id,
        created_at=now,
        updated_at=now,
    )
    db.add(series)
    db.flush()
    db.add_all(
        [
            PortfolioSeriesMedia(
                series_id=series.id,
                media_id=media[1].id,
                caption="第二张",
                sort_order=20,
                created_at=now,
            ),
            PortfolioSeriesMedia(
                series_id=series.id,
                media_id=media[0].id,
                caption="第一张",
                sort_order=10,
                created_at=now,
            ),
        ]
    )
    db.commit()

    result = AdminContentService().portfolio_detail(
        db, series.id, "https://example.com/media/public"
    )

    assert result["slug"] == "summer"
    assert [item["id"] for item in result["media"]] == [media[0].id, media[1].id]
    assert result["media"][0]["thumbnail_url"].endswith("0-thumb.jpg")
    assert result["media"][1]["caption"] == "第二张"

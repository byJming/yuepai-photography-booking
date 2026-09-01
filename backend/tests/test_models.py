from sqlalchemy import create_engine, inspect

from app.core.database import Base
from app.models import ALL_MODELS  # noqa: F401


def test_metadata_contains_production_tables() -> None:
    expected = {
        "users",
        "admin_users",
        "media_assets",
        "portfolio_series",
        "portfolio_series_media",
        "booking_option_groups",
        "booking_option_items",
        "availability_slots",
        "bookings",
        "booking_option_selections",
        "booking_events",
        "app_settings",
        "audit_logs",
        "data_deletion_requests",
    }
    assert expected <= set(Base.metadata.tables)


def test_metadata_can_create_empty_sqlite_schema() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    assert "bookings" in inspect(engine).get_table_names()


def test_booking_has_final_idempotency_constraint() -> None:
    table = Base.metadata.tables["bookings"]
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("user_id", "idempotency_key_hash") in unique_columns
    assert ("slot_id",) in unique_columns

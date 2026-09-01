import json
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command
from app.core.config import get_settings


def test_initial_migration_creates_usable_defaults(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    database_path = tmp_path / "migration.sqlite3"
    monkeypatch.setenv("MYSQL_DSN", f"sqlite+pysqlite:///{database_path.as_posix()}")
    get_settings.cache_clear()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite+pysqlite:///{database_path.as_posix()}")
    with engine.connect() as connection:
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        group_count = connection.scalar(text("SELECT COUNT(*) FROM booking_option_groups"))
        item_count = connection.scalar(text("SELECT COUNT(*) FROM booking_option_items"))
        brand = connection.scalar(
            text("SELECT value_json FROM app_settings WHERE setting_key = 'brand'")
        )
        policy_content = connection.scalar(
            text("SELECT value_json FROM app_settings WHERE setting_key = 'policy_content'")
        )
        booking_rules = connection.scalar(
            text("SELECT value_json FROM app_settings WHERE setting_key = 'booking_rules'")
        )
    admin_columns = {
        column["name"]: column for column in inspect(engine).get_columns("admin_users")
    }
    engine.dispose()
    get_settings.cache_clear()

    assert revision == "0003_expand_booking_horizon"
    assert group_count == 6
    assert item_count == 22
    assert admin_columns["totp_secret_ciphertext"]["nullable"] is True
    assert "totp_enabled" in admin_columns
    assert json.loads(str(brand))["name"] == "摄影预约"
    assert "privacy_and_display" in json.loads(str(policy_content))
    assert json.loads(str(booking_rules))["open_months"] == 12

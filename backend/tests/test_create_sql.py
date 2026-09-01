import re
from pathlib import Path

from sqlalchemy import Index, UniqueConstraint

from app.core.database import Base
from app.models import ALL_MODELS  # noqa: F401


def test_create_sql_contains_all_tables_and_safe_charset() -> None:
    sql = (Path(__file__).parents[2] / "deploy" / "mysql" / "create.sql").read_text(
        encoding="utf-8"
    )
    for table in (
        "users",
        "admin_users",
        "media_assets",
        "portfolio_series",
        "availability_slots",
        "bookings",
        "booking_events",
        "audit_logs",
    ):
        assert f"CREATE TABLE `{table}`" in sql
    assert "DEFAULT CHARSET=utf8mb4" in sql
    assert "MYSQL_PASSWORD" not in sql
    assert "FOREIGN_KEY_CHECKS" in sql
    assert "USE `yuepai_example`;" in sql
    assert "CREATE TABLE `alembic_version`" in sql
    assert "'0003_expand_booking_horizon'" in sql
    assert "'policy_content'" in sql
    assert '"open_months":12' in sql


def test_create_sql_seeds_a_usable_booking_form() -> None:
    sql = (Path(__file__).parents[2] / "deploy" / "mysql" / "create.sql").read_text(
        encoding="utf-8"
    )

    assert "INSERT INTO `booking_option_groups`" in sql
    assert "INSERT INTO `booking_option_items`" in sql
    for group_code in (
        "shoot_type",
        "style",
        "equipment_feel",
        "props",
        "budget",
        "location",
    ):
        assert f"'{group_code}'" in sql
    for item_code in (
        "portrait",
        "daily_natural",
        "camera",
        "budget_300_500",
        "lakeside",
        "custom",
    ):
        assert f"'{item_code}'" in sql


def test_create_sql_matches_model_tables_columns_and_named_constraints() -> None:
    sql = (Path(__file__).parents[2] / "deploy" / "mysql" / "create.sql").read_text(
        encoding="utf-8"
    )

    for table in Base.metadata.sorted_tables:
        match = re.search(
            rf"CREATE TABLE `{re.escape(table.name)}` \((.*?)\) ENGINE=InnoDB",
            sql,
            re.DOTALL,
        )
        assert match is not None, f"create.sql 缺少表 {table.name}"
        block = match.group(1)
        for column in table.columns:
            assert f"`{column.name}`" in block, f"create.sql 的 {table.name} 缺少列 {column.name}"
        named_constraints = {
            constraint.name
            for constraint in table.constraints
            if isinstance(constraint, UniqueConstraint) and constraint.name
        }
        named_indexes = {index.name for index in table.indexes if isinstance(index, Index)}
        for name in named_constraints | named_indexes:
            assert f"`{name}`" in block, f"create.sql 的 {table.name} 缺少约束或索引 {name}"

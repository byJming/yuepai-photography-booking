"""将可预约与可配置档期范围扩展到十二个月。

Revision ID: 0003_expand_booking_horizon
Revises: 0002_optional_admin_totp
Create Date: 2026-07-27
"""

from typing import Any

import sqlalchemy as sa

from alembic import op

revision = "0003_expand_booking_horizon"
down_revision = "0002_optional_admin_totp"
branch_labels = None
depends_on = None


def _booking_rules() -> tuple[sa.TableClause, Any]:
    table = sa.table(
        "app_settings",
        sa.column("setting_key", sa.String(64)),
        sa.column("value_json", sa.JSON()),
    )
    connection = op.get_bind()
    value = connection.execute(
        sa.select(table.c.value_json).where(table.c.setting_key == "booking_rules")
    ).scalar_one_or_none()
    return table, value


def upgrade() -> None:
    """保留其他预约规则，仅扩展仍使用旧默认值的开放月数。"""

    table, value = _booking_rules()
    if isinstance(value, dict) and int(value.get("open_months", 3)) <= 3:
        updated = {**value, "open_months": 12}
        op.execute(
            table.update().where(table.c.setting_key == "booking_rules").values(value_json=updated)
        )


def downgrade() -> None:
    """只回退本迁移设置的十二个月默认值。"""

    table, value = _booking_rules()
    if isinstance(value, dict) and value.get("open_months") == 12:
        updated = {**value, "open_months": 3}
        op.execute(
            table.update().where(table.c.setting_key == "booking_rules").values(value_json=updated)
        )

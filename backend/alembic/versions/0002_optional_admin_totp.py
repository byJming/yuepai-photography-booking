"""管理员动态验证码改为登录后可选启用。

Revision ID: 0002_optional_admin_totp
Revises: 0001_initial
Create Date: 2026-07-26
"""

import sqlalchemy as sa

from alembic import op

revision = "0002_optional_admin_totp"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """允许未绑定 TOTP 的管理员，并保留已有管理员的启用状态。"""

    columns = {
        column["name"]: column
        for column in sa.inspect(op.get_bind()).get_columns("admin_users")
    }
    secret_is_nullable = bool(columns["totp_secret_ciphertext"]["nullable"])
    totp_enabled_exists = "totp_enabled" in columns
    if not secret_is_nullable or not totp_enabled_exists:
        with op.batch_alter_table("admin_users") as batch_op:
            if not secret_is_nullable:
                batch_op.alter_column(
                    "totp_secret_ciphertext",
                    existing_type=sa.LargeBinary(512),
                    nullable=True,
                )
            if not totp_enabled_exists:
                batch_op.add_column(
                    sa.Column(
                        "totp_enabled",
                        sa.Boolean(),
                        nullable=False,
                        server_default=sa.false(),
                    )
                )
    admin_users = sa.table(
        "admin_users",
        sa.column("totp_secret_ciphertext", sa.LargeBinary(512)),
        sa.column("totp_enabled", sa.Boolean()),
    )
    op.execute(
        admin_users.update()
        .where(admin_users.c.totp_secret_ciphertext.is_not(None))
        .values(totp_enabled=True)
    )


def downgrade() -> None:
    """回退为强制 TOTP 结构；无密钥账号将无法继续完成 TOTP 登录。"""

    columns = {
        column["name"]: column
        for column in sa.inspect(op.get_bind()).get_columns("admin_users")
    }
    admin_users = sa.table(
        "admin_users",
        sa.column("totp_secret_ciphertext", sa.LargeBinary(512)),
    )
    op.execute(
        admin_users.update()
        .where(admin_users.c.totp_secret_ciphertext.is_(None))
        .values(totp_secret_ciphertext=b"")
    )
    secret_is_nullable = bool(columns["totp_secret_ciphertext"]["nullable"])
    totp_enabled_exists = "totp_enabled" in columns
    if secret_is_nullable or totp_enabled_exists:
        with op.batch_alter_table("admin_users") as batch_op:
            if secret_is_nullable:
                batch_op.alter_column(
                    "totp_secret_ciphertext",
                    existing_type=sa.LargeBinary(512),
                    nullable=False,
                )
            if totp_enabled_exists:
                batch_op.drop_column("totp_enabled")
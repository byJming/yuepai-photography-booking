from __future__ import annotations

import getpass
import sys

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import build_engine, build_session_factory
from app.core.security import hash_password
from app.models import AdminUser
from app.utils.time import utc_now


def main() -> None:
    """交互式创建默认未启用 TOTP 的管理员。"""

    settings = get_settings()
    username = input("管理员用户名：").strip()
    if not username or len(username) > 64:
        raise SystemExit("用户名不能为空且不能超过 64 个字符。")
    password = getpass.getpass("管理员密码（至少 12 位）：")
    confirmation = getpass.getpass("再次输入密码：")
    if password != confirmation:
        raise SystemExit("两次输入的密码不一致。")
    if len(password) < 12:
        raise SystemExit("管理员密码至少需要 12 位。")
    engine = build_engine(settings)
    factory = build_session_factory(engine)
    db = factory()
    try:
        if db.scalar(select(AdminUser.id).where(AdminUser.username == username)) is not None:
            raise SystemExit("该管理员用户名已存在。")
        now = utc_now()
        admin = AdminUser(
            username=username,
            password_hash=hash_password(password),
            totp_secret_ciphertext=None,
            totp_enabled=False,
            status="active",
            failed_login_count=0,
            password_changed_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(admin)
        db.commit()
        print("管理员创建成功。请登录管理后台，在“账户安全”中按需启用动态验证码。")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("已取消。")
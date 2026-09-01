from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.errors import DomainValidationError
from app.models import AdminUser
from app.services.admin_content import AdminContentService


def build_db() -> tuple[Session, AdminUser]:
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
    db.commit()
    return db, admin


def test_policy_content_setting_is_public_and_validated() -> None:
    db, admin = build_db()
    value = {
        "service_scope": "单摄影师个人摄影服务。",
        "schedule_and_pricing": "档期和费用人工确认。",
        "safety_and_reschedule": "首次合作优先公共场所。",
        "privacy_and_display": "预约信息只用于沟通。",
        "cancellation_rules": "未确认预约可以取消。",
    }

    setting = AdminContentService().patch_setting(
        db, admin.id, "policy_content", value, "request-1"
    )

    assert setting.is_public is True
    assert setting.value_json == value


def test_policy_content_rejects_empty_required_text() -> None:
    db, admin = build_db()

    with pytest.raises(DomainValidationError):
        AdminContentService().patch_setting(
            db,
            admin.id,
            "policy_content",
            {
                "service_scope": "",
                "schedule_and_pricing": "档期和费用人工确认。",
                "safety_and_reschedule": "首次合作优先公共场所。",
                "privacy_and_display": "预约信息只用于沟通。",
                "cancellation_rules": "未确认预约可以取消。",
            },
            "request-2",
        )

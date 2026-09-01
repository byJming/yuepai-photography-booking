from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import build_engine
from app.core.security import FieldCipher
from app.services.data_retention import DataRetentionService


def main() -> None:
    """按生产配置执行一次预约敏感字段保留策略清理。"""

    settings = get_settings()
    engine = build_engine(settings)
    try:
        with Session(engine) as db:
            result = DataRetentionService(
                FieldCipher(settings.field_encryption_key_v1)
            ).run_policy_cleanup(db)
        print(json.dumps(result, ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

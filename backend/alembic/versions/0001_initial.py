"""初始数据库结构。

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-26
"""

from datetime import UTC, datetime

from alembic import op

from app.core.database import Base
from app.models import (
    ALL_MODELS,  # noqa: F401
    AppSetting,
    BookingOptionGroup,
    BookingOptionItem,
)

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """开发和测试环境从空库创建结构；生产首次安装优先执行 create.sql。"""

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)
    now = datetime.now(UTC).replace(tzinfo=None)
    op.bulk_insert(
        AppSetting.__table__,
        [
            {
                "setting_key": "brand",
                "value_json": {
                    "name": "摄影预约",
                    "eyebrow": "自然人像 · 城市记录",
                    "monthly_title": "记录平常而珍贵的瞬间",
                    "monthly_subtitle": "最终品牌名与主题可在管理后台修改。",
                    "availability_text": "近期可约",
                    "service_area": "请与摄影师确认",
                    "about_text": "专注自然、真实的个人摄影记录。",
                },
                "is_public": True,
                "updated_by_admin_id": None,
                "updated_at": now,
            },
            {
                "setting_key": "feature_flags",
                "value_json": {"subscription_message": False, "reference_upload": False},
                "is_public": True,
                "updated_by_admin_id": None,
                "updated_at": now,
            },
            {
                "setting_key": "policy_versions",
                "value_json": {"privacy": "2026-07-26", "service_terms": "2026-07-26"},
                "is_public": True,
                "updated_by_admin_id": None,
                "updated_at": now,
            },
            {
                "setting_key": "policy_content",
                "value_json": {
                    "service_scope": "当前提供单摄影师个人写真、情侣记录、毕业季和城市跟拍等摄影服务。城市跟拍以摄影为核心，不提供社交、陪伴或撮合服务。",
                    "schedule_and_pricing": "小程序提交的是预约意向，档期、地点和最终费用由摄影师沟通确认，本版本不提供在线支付。",
                    "safety_and_reschedule": "首次合作优先选择公共场所，未成年人需要监护人参与。改期和取消请尽早沟通。",
                    "privacy_and_display": "联系人、手机号、意向日期、地点、选择项和备注只用于预约沟通及履约。作品公开展示需要另行取得授权。",
                    "cancellation_rules": "未确认预约可以在小程序中取消；已确认预约请联系摄影师处理。个人数据删除申请需要人工核对未完成预约。",
                },
                "is_public": True,
                "updated_by_admin_id": None,
                "updated_at": now,
            },            {
                "setting_key": "booking_rules",
                "value_json": {
                    "open_months": 3,
                    "confirmed_customer_cancel": False,
                    "data_retention_completed_months": 12,
                    "data_retention_cancelled_months": 6,
                },
                "is_public": False,
                "updated_by_admin_id": None,
                "updated_at": now,
            },
        ],
    )
    op.bulk_insert(
        BookingOptionGroup.__table__,
        [
            {
                "id": 1,
                "code": "shoot_type",
                "name": "拍摄类型",
                "selection_mode": "single",
                "is_required": True,
                "min_select": 1,
                "max_select": 1,
                "status": "active",
                "sort_order": 10,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": 2,
                "code": "style",
                "name": "拍摄风格",
                "selection_mode": "single",
                "is_required": True,
                "min_select": 1,
                "max_select": 1,
                "status": "active",
                "sort_order": 20,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": 3,
                "code": "equipment_feel",
                "name": "成片质感",
                "selection_mode": "single",
                "is_required": True,
                "min_select": 1,
                "max_select": 1,
                "status": "active",
                "sort_order": 30,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": 4,
                "code": "props",
                "name": "拍摄道具",
                "selection_mode": "multiple",
                "is_required": False,
                "min_select": 0,
                "max_select": 3,
                "status": "active",
                "sort_order": 40,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": 5,
                "code": "budget",
                "name": "预算范围",
                "selection_mode": "single",
                "is_required": True,
                "min_select": 1,
                "max_select": 1,
                "status": "active",
                "sort_order": 50,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": 6,
                "code": "location",
                "name": "意向地点",
                "selection_mode": "single",
                "is_required": True,
                "min_select": 1,
                "max_select": 1,
                "status": "active",
                "sort_order": 60,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )
    item_rows = [
        (1, 1, "portrait", "个人写真", "1 人，约 1.5 小时", {"mark": "人像"}),
        (2, 1, "couple", "情侣记录", "2 人，约 2 小时", {"mark": "双人"}),
        (3, 1, "graduation", "毕业季", "1–4 人，约 2 小时", {"mark": "纪念"}),
        (4, 1, "city", "城市跟拍", "边走边拍，约 2 小时", {"mark": "散步"}),
        (5, 2, "daily_natural", "日常自然", "轻松、明亮、少摆拍", {}),
        (6, 2, "soft_film", "温柔胶片", "低饱和、颗粒感、慢节奏", {}),
        (7, 2, "city_documentary", "城市纪实", "真实互动和生活感", {}),
        (8, 3, "camera", "细腻清晰", "使用相机拍摄，画质更稳定", {}),
        (9, 3, "phone", "轻松随拍", "使用手机拍摄，更有生活记录感", {}),
        (10, 3, "hybrid", "灵活搭配", "根据场景切换相机和手机", {}),
        (11, 4, "flowers", "鲜花", "适合自然人像和纪念拍摄", {}),
        (12, 4, "book", "书籍", "适合安静、生活化的画面", {}),
        (13, 4, "picnic", "野餐布置", "适合公园和户外场景", {}),
        (14, 5, "budget_under_300", "300 元以内", "最终费用由摄影师沟通确认", {"max": 300}),
        (
            15,
            5,
            "budget_300_500",
            "300–500 元",
            "最终费用由摄影师沟通确认",
            {"min": 300, "max": 500},
        ),
        (
            16,
            5,
            "budget_500_800",
            "500–800 元",
            "最终费用由摄影师沟通确认",
            {"min": 500, "max": 800},
        ),
        (17, 5, "budget_800_plus", "800 元以上", "最终费用由摄影师沟通确认", {"min": 800}),
        (18, 5, "budget_discuss", "希望沟通后确定", "提交意向后再确认预算", {}),
        (19, 6, "lakeside", "湖边绿道", "清透自然", {}),
        (20, 6, "city", "城市街区", "生活纪实", {}),
        (21, 6, "campus", "校园", "适合毕业季和纪念拍摄", {}),
        (22, 6, "custom", "一起商量", "填写意向区域，提交后沟通", {}),
    ]
    op.bulk_insert(
        BookingOptionItem.__table__,
        [
            {
                "id": item_id,
                "group_id": group_id,
                "code": code,
                "name": name,
                "description": description,
                "reference_media_id": None,
                "metadata_json": metadata,
                "status": "active",
                "sort_order": sort_order * 10,
                "created_at": now,
                "updated_at": now,
            }
            for sort_order, (item_id, group_id, code, name, description, metadata) in enumerate(
                item_rows, start=1
            )
        ],
    )


def downgrade() -> None:
    """仅供空测试库使用，生产环境禁止直接执行破坏性降级。"""

    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)

-- 悦拍生产数据库初始结构（MySQL 5.7 / 手动执行）
-- 执行前请确认 yuepai_example 为空库，并完成备份。

USE `yuepai_example`;

SET NAMES utf8mb4;
SET time_zone = '+00:00';
SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE `alembic_version` (
  `version_num` VARCHAR(32) NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `alembic_version` (`version_num`) VALUES ('0003_expand_booking_horizon')
ON DUPLICATE KEY UPDATE `version_num` = VALUES(`version_num`);

CREATE TABLE `users` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `openid_hash` BINARY(32) NOT NULL,
  `openid_ciphertext` VARBINARY(255) NULL,
  `status` VARCHAR(16) NOT NULL,
  `last_login_at` DATETIME(3) NULL,
  `created_at` DATETIME(3) NOT NULL,
  `updated_at` DATETIME(3) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_users_openid_hash` (`openid_hash`),
  KEY `ix_users_status_login` (`status`, `last_login_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `admin_users` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(64) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `totp_secret_ciphertext` VARBINARY(512) NULL,
  `totp_enabled` TINYINT(1) NOT NULL DEFAULT 0,
  `status` VARCHAR(16) NOT NULL,
  `failed_login_count` SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  `locked_until` DATETIME(3) NULL,
  `last_login_at` DATETIME(3) NULL,
  `password_changed_at` DATETIME(3) NOT NULL,
  `created_at` DATETIME(3) NOT NULL,
  `updated_at` DATETIME(3) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_admin_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `media_assets` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `storage_provider` VARCHAR(16) NOT NULL,
  `object_key` VARCHAR(512) NOT NULL,
  `thumbnail_object_key` VARCHAR(512) NULL,
  `visibility` VARCHAR(16) NOT NULL,
  `kind` VARCHAR(32) NOT NULL,
  `mime_type` VARCHAR(64) NOT NULL,
  `file_size` BIGINT UNSIGNED NOT NULL,
  `width` INT UNSIGNED NOT NULL,
  `height` INT UNSIGNED NOT NULL,
  `sha256` CHAR(64) NOT NULL,
  `status` VARCHAR(16) NOT NULL,
  `created_by_admin_id` BIGINT UNSIGNED NOT NULL,
  `created_at` DATETIME(3) NOT NULL,
  `updated_at` DATETIME(3) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_media_provider_key` (`storage_provider`, `object_key`(191)),
  KEY `ix_media_kind_status` (`kind`, `status`),
  CONSTRAINT `fk_media_admin` FOREIGN KEY (`created_by_admin_id`) REFERENCES `admin_users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `portfolio_series` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `slug` VARCHAR(64) NOT NULL,
  `title` VARCHAR(80) NOT NULL,
  `subtitle` VARCHAR(120) NULL,
  `description` TEXT NULL,
  `category_code` VARCHAR(32) NOT NULL,
  `style_tags_json` JSON NOT NULL,
  `location_text` VARCHAR(100) NULL,
  `shot_on` DATE NULL,
  `cover_media_id` BIGINT UNSIGNED NULL,
  `status` VARCHAR(16) NOT NULL,
  `sort_order` INT NOT NULL DEFAULT 0,
  `published_at` DATETIME(3) NULL,
  `created_by_admin_id` BIGINT UNSIGNED NOT NULL,
  `created_at` DATETIME(3) NOT NULL,
  `updated_at` DATETIME(3) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_portfolio_slug` (`slug`),
  KEY `ix_portfolio_status_sort` (`status`, `sort_order`, `published_at`),
  KEY `ix_portfolio_category_status` (`category_code`, `status`),
  KEY `ix_portfolio_cover` (`cover_media_id`),
  CONSTRAINT `fk_portfolio_cover` FOREIGN KEY (`cover_media_id`) REFERENCES `media_assets` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_portfolio_admin` FOREIGN KEY (`created_by_admin_id`) REFERENCES `admin_users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `portfolio_series_media` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `series_id` BIGINT UNSIGNED NOT NULL,
  `media_id` BIGINT UNSIGNED NOT NULL,
  `caption` VARCHAR(200) NULL,
  `sort_order` INT NOT NULL,
  `created_at` DATETIME(3) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_series_media` (`series_id`, `media_id`),
  UNIQUE KEY `uq_series_sort` (`series_id`, `sort_order`),
  CONSTRAINT `fk_series_media_series` FOREIGN KEY (`series_id`) REFERENCES `portfolio_series` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_series_media_asset` FOREIGN KEY (`media_id`) REFERENCES `media_assets` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `booking_option_groups` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `code` VARCHAR(32) NOT NULL,
  `name` VARCHAR(40) NOT NULL,
  `selection_mode` VARCHAR(16) NOT NULL,
  `is_required` TINYINT(1) NOT NULL DEFAULT 0,
  `min_select` TINYINT UNSIGNED NOT NULL DEFAULT 0,
  `max_select` TINYINT UNSIGNED NOT NULL DEFAULT 1,
  `status` VARCHAR(16) NOT NULL,
  `sort_order` INT NOT NULL DEFAULT 0,
  `created_at` DATETIME(3) NOT NULL,
  `updated_at` DATETIME(3) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_option_group_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `booking_option_items` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `group_id` BIGINT UNSIGNED NOT NULL,
  `code` VARCHAR(32) NOT NULL,
  `name` VARCHAR(60) NOT NULL,
  `description` VARCHAR(300) NULL,
  `reference_media_id` BIGINT UNSIGNED NULL,
  `metadata_json` JSON NOT NULL,
  `status` VARCHAR(16) NOT NULL,
  `sort_order` INT NOT NULL DEFAULT 0,
  `created_at` DATETIME(3) NOT NULL,
  `updated_at` DATETIME(3) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_option_group_item_code` (`group_id`, `code`),
  KEY `ix_option_group_status_sort` (`group_id`, `status`, `sort_order`),
  KEY `ix_option_reference_media` (`reference_media_id`),
  CONSTRAINT `fk_option_item_group` FOREIGN KEY (`group_id`) REFERENCES `booking_option_groups` (`id`),
  CONSTRAINT `fk_option_reference_media` FOREIGN KEY (`reference_media_id`) REFERENCES `media_assets` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `availability_slots` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `start_at` DATETIME(3) NOT NULL,
  `end_at` DATETIME(3) NOT NULL,
  `status` VARCHAR(16) NOT NULL,
  `public_note` VARCHAR(100) NULL,
  `internal_note_ciphertext` VARBINARY(1024) NULL,
  `version` INT UNSIGNED NOT NULL DEFAULT 1,
  `created_by_admin_id` BIGINT UNSIGNED NOT NULL,
  `created_at` DATETIME(3) NOT NULL,
  `updated_at` DATETIME(3) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_slot_times` (`start_at`, `end_at`),
  KEY `ix_slot_status_start` (`status`, `start_at`),
  CONSTRAINT `fk_slot_admin` FOREIGN KEY (`created_by_admin_id`) REFERENCES `admin_users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `bookings` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `booking_no` CHAR(20) NOT NULL,
  `user_id` BIGINT UNSIGNED NOT NULL,
  `idempotency_key_hash` BINARY(32) NOT NULL,
  `request_fingerprint` BINARY(32) NOT NULL,
  `status` VARCHAR(32) NOT NULL,
  `requested_date` DATE NOT NULL,
  `requested_period_code` VARCHAR(32) NOT NULL,
  `slot_id` BIGINT UNSIGNED NULL,
  `participant_count` TINYINT UNSIGNED NOT NULL,
  `budget_code` VARCHAR(32) NULL,
  `location_type` VARCHAR(16) NOT NULL,
  `location_code` VARCHAR(32) NULL,
  `custom_location_ciphertext` VARBINARY(1024) NULL,
  `contact_name_ciphertext` VARBINARY(512) NOT NULL,
  `contact_phone_ciphertext` VARBINARY(512) NOT NULL,
  `contact_phone_last4` CHAR(4) NOT NULL,
  `remark_ciphertext` VARBINARY(2048) NULL,
  `privacy_policy_version` VARCHAR(32) NOT NULL,
  `service_terms_version` VARCHAR(32) NOT NULL,
  `consented_at` DATETIME(3) NOT NULL,
  `version` INT UNSIGNED NOT NULL DEFAULT 1,
  `submitted_at` DATETIME(3) NOT NULL,
  `confirmed_at` DATETIME(3) NULL,
  `completed_at` DATETIME(3) NULL,
  `cancelled_at` DATETIME(3) NULL,
  `sensitive_data_cleared_at` DATETIME(3) NULL,
  `created_at` DATETIME(3) NOT NULL,
  `updated_at` DATETIME(3) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_booking_no` (`booking_no`),
  UNIQUE KEY `uq_booking_slot` (`slot_id`),
  UNIQUE KEY `uq_booking_idempotency` (`user_id`, `idempotency_key_hash`),
  KEY `ix_booking_user_updated` (`user_id`, `updated_at`),
  KEY `ix_booking_status_date` (`status`, `requested_date`),
  KEY `ix_booking_phone_created` (`contact_phone_last4`, `created_at`),
  CONSTRAINT `fk_booking_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_booking_slot` FOREIGN KEY (`slot_id`) REFERENCES `availability_slots` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `booking_option_selections` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `booking_id` BIGINT UNSIGNED NOT NULL,
  `option_item_id` BIGINT UNSIGNED NULL,
  `group_code_snapshot` VARCHAR(32) NOT NULL,
  `item_code_snapshot` VARCHAR(32) NOT NULL,
  `item_name_snapshot` VARCHAR(60) NOT NULL,
  `created_at` DATETIME(3) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_booking_selection` (`booking_id`, `group_code_snapshot`, `item_code_snapshot`),
  KEY `ix_selection_option_item` (`option_item_id`),
  CONSTRAINT `fk_selection_booking` FOREIGN KEY (`booking_id`) REFERENCES `bookings` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_selection_option_item` FOREIGN KEY (`option_item_id`) REFERENCES `booking_option_items` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `booking_events` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `booking_id` BIGINT UNSIGNED NOT NULL,
  `actor_user_id` BIGINT UNSIGNED NULL,
  `actor_admin_user_id` BIGINT UNSIGNED NULL,
  `actor_type` VARCHAR(16) NOT NULL,
  `event_type` VARCHAR(32) NOT NULL,
  `from_status` VARCHAR(32) NULL,
  `to_status` VARCHAR(32) NULL,
  `public_message` VARCHAR(300) NULL,
  `internal_note_ciphertext` VARBINARY(2048) NULL,
  `metadata_json` JSON NOT NULL,
  `created_at` DATETIME(3) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_booking_event_created` (`booking_id`, `created_at`),
  KEY `ix_event_actor_user` (`actor_user_id`),
  KEY `ix_event_actor_admin` (`actor_admin_user_id`),
  CONSTRAINT `fk_event_booking` FOREIGN KEY (`booking_id`) REFERENCES `bookings` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_event_user` FOREIGN KEY (`actor_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_event_admin` FOREIGN KEY (`actor_admin_user_id`) REFERENCES `admin_users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `app_settings` (
  `setting_key` VARCHAR(64) NOT NULL,
  `value_json` JSON NOT NULL,
  `is_public` TINYINT(1) NOT NULL DEFAULT 0,
  `updated_by_admin_id` BIGINT UNSIGNED NULL,
  `updated_at` DATETIME(3) NOT NULL,
  PRIMARY KEY (`setting_key`),
  KEY `ix_setting_admin` (`updated_by_admin_id`),
  CONSTRAINT `fk_setting_admin` FOREIGN KEY (`updated_by_admin_id`) REFERENCES `admin_users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `audit_logs` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `actor_admin_user_id` BIGINT UNSIGNED NOT NULL,
  `action` VARCHAR(64) NOT NULL,
  `entity_type` VARCHAR(32) NOT NULL,
  `entity_id` BIGINT UNSIGNED NULL,
  `request_id` CHAR(36) NOT NULL,
  `metadata_json` JSON NOT NULL,
  `created_at` DATETIME(3) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_audit_actor_created` (`actor_admin_user_id`, `created_at`),
  KEY `ix_audit_entity_created` (`entity_type`, `entity_id`, `created_at`),
  CONSTRAINT `fk_audit_admin` FOREIGN KEY (`actor_admin_user_id`) REFERENCES `admin_users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `data_deletion_requests` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT UNSIGNED NOT NULL,
  `status` VARCHAR(16) NOT NULL,
  `processed_by_admin_id` BIGINT UNSIGNED NULL,
  `processed_at` DATETIME(3) NULL,
  `created_at` DATETIME(3) NOT NULL,
  `updated_at` DATETIME(3) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_deletion_status_created` (`status`, `created_at`),
  KEY `ix_deletion_user` (`user_id`),
  KEY `ix_deletion_admin` (`processed_by_admin_id`),
  CONSTRAINT `fk_deletion_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_deletion_admin` FOREIGN KEY (`processed_by_admin_id`) REFERENCES `admin_users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `app_settings` (`setting_key`, `value_json`, `is_public`, `updated_by_admin_id`, `updated_at`) VALUES
  ('brand', '{"name":"摄影预约","eyebrow":"自然人像 · 城市记录","monthly_title":"记录平常而珍贵的瞬间","monthly_subtitle":"最终品牌名与主题可在管理后台修改。","availability_text":"近期可约","service_area":"请与摄影师确认","about_text":"专注自然、真实的个人摄影记录。"}', 1, NULL, UTC_TIMESTAMP(3)),
  ('feature_flags', '{"subscription_message":false,"reference_upload":false}', 1, NULL, UTC_TIMESTAMP(3)),
  ('policy_versions', '{"privacy":"2026-07-26","service_terms":"2026-07-26"}', 1, NULL, UTC_TIMESTAMP(3)),
  ('policy_content', '{"service_scope":"当前提供单摄影师个人写真、情侣记录、毕业季和城市跟拍等摄影服务。城市跟拍以摄影为核心，不提供社交、陪伴或撮合服务。","schedule_and_pricing":"小程序提交的是预约意向，档期、地点和最终费用由摄影师沟通确认，本版本不提供在线支付。","safety_and_reschedule":"首次合作优先选择公共场所，未成年人需要监护人参与。改期和取消请尽早沟通。","privacy_and_display":"联系人、手机号、意向日期、地点、选择项和备注只用于预约沟通及履约。作品公开展示需要另行取得授权。","cancellation_rules":"未确认预约可以在小程序中取消；已确认预约请联系摄影师处理。个人数据删除申请需要人工核对未完成预约。"}', 1, NULL, UTC_TIMESTAMP(3)),
  ('booking_rules', '{"open_months":12,"confirmed_customer_cancel":false,"data_retention_completed_months":12,"data_retention_cancelled_months":6}', 0, NULL, UTC_TIMESTAMP(3))
ON DUPLICATE KEY UPDATE `setting_key` = VALUES(`setting_key`);

INSERT INTO `booking_option_groups`
  (`id`, `code`, `name`, `selection_mode`, `is_required`, `min_select`, `max_select`, `status`, `sort_order`, `created_at`, `updated_at`)
VALUES
  (1, 'shoot_type', '拍摄类型', 'single', 1, 1, 1, 'active', 10, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (2, 'style', '拍摄风格', 'single', 1, 1, 1, 'active', 20, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (3, 'equipment_feel', '成片质感', 'single', 1, 1, 1, 'active', 30, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (4, 'props', '拍摄道具', 'multiple', 0, 0, 3, 'active', 40, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (5, 'budget', '预算范围', 'single', 1, 1, 1, 'active', 50, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (6, 'location', '意向地点', 'single', 1, 1, 1, 'active', 60, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3))
ON DUPLICATE KEY UPDATE
  `name` = VALUES(`name`),
  `selection_mode` = VALUES(`selection_mode`),
  `is_required` = VALUES(`is_required`),
  `min_select` = VALUES(`min_select`),
  `max_select` = VALUES(`max_select`),
  `status` = VALUES(`status`),
  `sort_order` = VALUES(`sort_order`),
  `updated_at` = VALUES(`updated_at`);

INSERT INTO `booking_option_items`
  (`id`, `group_id`, `code`, `name`, `description`, `reference_media_id`, `metadata_json`, `status`, `sort_order`, `created_at`, `updated_at`)
VALUES
  (1, 1, 'portrait', '个人写真', '1 人，约 1.5 小时', NULL, '{"mark":"人像"}', 'active', 10, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (2, 1, 'couple', '情侣记录', '2 人，约 2 小时', NULL, '{"mark":"双人"}', 'active', 20, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (3, 1, 'graduation', '毕业季', '1–4 人，约 2 小时', NULL, '{"mark":"纪念"}', 'active', 30, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (4, 1, 'city', '城市跟拍', '边走边拍，约 2 小时', NULL, '{"mark":"散步"}', 'active', 40, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (5, 2, 'daily_natural', '日常自然', '轻松、明亮、少摆拍', NULL, '{}', 'active', 10, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (6, 2, 'soft_film', '温柔胶片', '低饱和、颗粒感、慢节奏', NULL, '{}', 'active', 20, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (7, 2, 'city_documentary', '城市纪实', '真实互动和生活感', NULL, '{}', 'active', 30, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (8, 3, 'camera', '细腻清晰', '使用相机拍摄，画质更稳定', NULL, '{}', 'active', 10, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (9, 3, 'phone', '轻松随拍', '使用手机拍摄，更有生活记录感', NULL, '{}', 'active', 20, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (10, 3, 'hybrid', '灵活搭配', '根据场景切换相机和手机', NULL, '{}', 'active', 30, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (11, 4, 'flowers', '鲜花', '适合自然人像和纪念拍摄', NULL, '{}', 'active', 10, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (12, 4, 'book', '书籍', '适合安静、生活化的画面', NULL, '{}', 'active', 20, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (13, 4, 'picnic', '野餐布置', '适合公园和户外场景', NULL, '{}', 'active', 30, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (14, 5, 'budget_under_300', '300 元以内', '最终费用由摄影师沟通确认', NULL, '{"max":300}', 'active', 10, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (15, 5, 'budget_300_500', '300–500 元', '最终费用由摄影师沟通确认', NULL, '{"min":300,"max":500}', 'active', 20, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (16, 5, 'budget_500_800', '500–800 元', '最终费用由摄影师沟通确认', NULL, '{"min":500,"max":800}', 'active', 30, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (17, 5, 'budget_800_plus', '800 元以上', '最终费用由摄影师沟通确认', NULL, '{"min":800}', 'active', 40, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (18, 5, 'budget_discuss', '希望沟通后确定', '提交意向后再确认预算', NULL, '{}', 'active', 50, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (19, 6, 'lakeside', '湖边绿道', '清透自然', NULL, '{}', 'active', 10, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (20, 6, 'city', '城市街区', '生活纪实', NULL, '{}', 'active', 20, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (21, 6, 'campus', '校园', '适合毕业季和纪念拍摄', NULL, '{}', 'active', 30, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3)),
  (22, 6, 'custom', '一起商量', '填写意向区域，提交后沟通', NULL, '{}', 'active', 40, UTC_TIMESTAMP(3), UTC_TIMESTAMP(3))
ON DUPLICATE KEY UPDATE
  `name` = VALUES(`name`),
  `description` = VALUES(`description`),
  `metadata_json` = VALUES(`metadata_json`),
  `status` = VALUES(`status`),
  `sort_order` = VALUES(`sort_order`),
  `updated_at` = VALUES(`updated_at`);

SET FOREIGN_KEY_CHECKS = 1;

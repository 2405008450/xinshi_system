-- 资源开拓独立数据结构；重复执行不覆盖已有配置或业务记录。
BEGIN;
CREATE TABLE IF NOT EXISTS resource_development_option (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), kind varchar(20) NOT NULL,
 category varchar(20) NOT NULL DEFAULT '', name varchar(100) NOT NULL,
 code varchar(30) UNIQUE, description text NOT NULL DEFAULT '', revision integer NOT NULL DEFAULT 1,
 UNIQUE(kind, name)
);
CREATE TABLE IF NOT EXISTS resource_development_counter (
 platform_id uuid REFERENCES resource_development_option(id), work_date date,
 value integer NOT NULL DEFAULT 0, PRIMARY KEY(platform_id, work_date)
);
CREATE TABLE IF NOT EXISTS resource_development_record (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), greeting_no varchar(80) NOT NULL UNIQUE,
 platform_id uuid NOT NULL REFERENCES resource_development_option(id), work_date date NOT NULL,
 owner_id uuid NOT NULL REFERENCES app_user(id), full_name varchar(255) NOT NULL,
 account_id uuid REFERENCES resource_development_option(id), phone varchar(100) NOT NULL DEFAULT '',
 wechat varchar(100) NOT NULL DEFAULT '', wechat_status varchar(100) NOT NULL DEFAULT '未处理',
 enterprise_status varchar(100) NOT NULL DEFAULT '未处理', follow_up text NOT NULL DEFAULT '',
 remarks text NOT NULL DEFAULT '', person_id uuid REFERENCES resource_person(id) ON DELETE SET NULL,
 duplicate_note text NOT NULL DEFAULT '', created_by uuid NOT NULL REFERENCES app_user(id),
 updated_by uuid NOT NULL REFERENCES app_user(id), created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP, revision integer NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS ix_resource_development_record_work_date ON resource_development_record(work_date);
CREATE INDEX IF NOT EXISTS ix_resource_development_record_owner_id ON resource_development_record(owner_id);
CREATE INDEX IF NOT EXISTS ix_resource_development_record_platform_id ON resource_development_record(platform_id);
CREATE INDEX IF NOT EXISTS ix_resource_development_record_updated_at ON resource_development_record(updated_at);
CREATE TABLE IF NOT EXISTS resource_development_language (
 record_id uuid REFERENCES resource_development_record(id) ON DELETE CASCADE,
 language_id uuid REFERENCES interpretation_language(id), PRIMARY KEY(record_id, language_id)
);
CREATE TABLE IF NOT EXISTS resource_development_action (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), record_id uuid NOT NULL REFERENCES resource_development_record(id) ON DELETE CASCADE,
 channel varchar(20) NOT NULL, status varchar(100) NOT NULL, request_number integer NOT NULL DEFAULT 0,
 action_date date NOT NULL, operator_id uuid NOT NULL REFERENCES app_user(id), account_id uuid REFERENCES resource_development_option(id),
 created_by uuid NOT NULL REFERENCES app_user(id), updated_by uuid NOT NULL REFERENCES app_user(id),
 created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_resource_development_action_record_id ON resource_development_action(record_id);
CREATE TABLE IF NOT EXISTS resource_development_work (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), work_date date NOT NULL, owner_id uuid NOT NULL REFERENCES app_user(id),
 periods json NOT NULL DEFAULT '[]', deduction integer NOT NULL DEFAULT 0 CHECK(deduction >= 0),
 duration_minutes integer NOT NULL DEFAULT 0 CHECK(duration_minutes >= 0), completed boolean,
 explanation text NOT NULL DEFAULT '', revision integer NOT NULL DEFAULT 1, updated_by uuid NOT NULL REFERENCES app_user(id),
 UNIQUE(work_date, owner_id)
);
CREATE INDEX IF NOT EXISTS ix_resource_development_work_work_date ON resource_development_work(work_date);
CREATE INDEX IF NOT EXISTS ix_resource_development_work_owner_id ON resource_development_work(owner_id);
CREATE TABLE IF NOT EXISTS resource_development_screenshot (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), work_id uuid NOT NULL REFERENCES resource_development_work(id) ON DELETE CASCADE,
 name varchar(255) NOT NULL, content_type varchar(50) NOT NULL, content bytea NOT NULL,
 created_by uuid NOT NULL REFERENCES app_user(id), created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_resource_development_screenshot_work_id ON resource_development_screenshot(work_id);
CREATE TABLE IF NOT EXISTS resource_development_audit (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), entity_id uuid NOT NULL, entity_type varchar(30) NOT NULL,
 actor_id uuid NOT NULL REFERENCES app_user(id), action varchar(30) NOT NULL,
 before json NOT NULL DEFAULT '{}', after json NOT NULL DEFAULT '{}', created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_resource_development_audit_entity_id ON resource_development_audit(entity_id);
INSERT INTO resource_development_option(kind, category, name, code) VALUES
 ('platform','national','BOSS 1','BOSS1'), ('platform','national','BOSS 2','BOSS2'), ('platform','national','BOSS 3','BOSS3'),
 ('platform','national','智联招聘1','ZL1'), ('platform','national','智联招聘2','ZL2'), ('platform','national','智联招聘3','ZL3'),
 ('platform','national','前程无忧主号','QCWY1'), ('platform','national','前程无忧小号','QCWY2'),
 ('platform','national','小红书招聘号','XHS'), ('platform','national','鱼泡','YP'),
 ('platform','local','温州招聘网','WZZP'), ('platform','local','泉州招聘网','QZZP'),
 ('platform','international','HiredChina','HIREDCHINA'), ('platform','international','Proz','PROZ'),
 ('account','','HR4',NULL), ('account','','HR5',NULL), ('account','','HR6',NULL),
 ('account','','HR4企微',NULL), ('account','','HR5企微',NULL), ('account','','HR6企微',NULL)
ON CONFLICT(kind,name) DO NOTHING;
COMMIT;

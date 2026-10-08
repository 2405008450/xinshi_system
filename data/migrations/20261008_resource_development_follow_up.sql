-- 纯文字跟进独立明细；不改写历史原文和原有状态跟进。
BEGIN;
CREATE TABLE IF NOT EXISTS resource_development_follow_up (
 id uuid PRIMARY KEY,
 record_id uuid NOT NULL REFERENCES resource_development_record(id) ON DELETE CASCADE,
 content text NOT NULL CHECK (char_length(btrim(content)) BETWEEN 1 AND 20000),
 operator_id uuid NOT NULL REFERENCES app_user(id),
 created_at timestamp NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Hong_Kong')
);
CREATE INDEX IF NOT EXISTS ix_resource_development_follow_up_record_time
 ON resource_development_follow_up(record_id, created_at, id);
COMMIT;

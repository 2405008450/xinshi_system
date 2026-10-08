-- 推荐拓展独立台账；重复执行不会覆盖业务数据。
BEGIN;
CREATE TABLE IF NOT EXISTS referral_development_record (
 id uuid PRIMARY KEY, work_date date NOT NULL, full_name varchar(255) NOT NULL,
 wechat varchar(100) NOT NULL DEFAULT '', pull_description text NOT NULL DEFAULT '',
 moments_description text NOT NULL DEFAULT '', groups_description text NOT NULL DEFAULT '',
 amount numeric(12,2) NOT NULL CHECK(amount >= 0), payment_status varchar(20) NOT NULL DEFAULT 'unpaid' CHECK(payment_status IN ('unpaid','paid')),
 payment_date date, remarks text NOT NULL DEFAULT '', created_by uuid NOT NULL REFERENCES app_user(id),
 updated_by uuid NOT NULL REFERENCES app_user(id), created_at timestamp NOT NULL, updated_at timestamp NOT NULL,
 revision integer NOT NULL DEFAULT 1 CHECK(revision > 0),
 CHECK((payment_status='paid' AND payment_date IS NOT NULL) OR (payment_status='unpaid' AND payment_date IS NULL))
);
CREATE INDEX IF NOT EXISTS ix_referral_development_record_work_date ON referral_development_record(work_date);
CREATE INDEX IF NOT EXISTS ix_referral_development_record_created_by ON referral_development_record(created_by);
CREATE INDEX IF NOT EXISTS ix_referral_development_record_payment_status ON referral_development_record(payment_status);
CREATE INDEX IF NOT EXISTS ix_referral_record_updated_at ON referral_development_record(updated_at);
CREATE TABLE IF NOT EXISTS referral_development_image (
 id uuid PRIMARY KEY, record_id uuid NOT NULL REFERENCES referral_development_record(id) ON DELETE CASCADE,
 category varchar(20) NOT NULL CHECK(category IN ('pull','moments','groups','qr')), name varchar(255) NOT NULL,
 content_type varchar(30) NOT NULL, content bytea NOT NULL, created_by uuid NOT NULL REFERENCES app_user(id), created_at timestamp NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_referral_development_image_record_id ON referral_development_image(record_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_referral_image_qr ON referral_development_image(record_id) WHERE category='qr';
CREATE TABLE IF NOT EXISTS referral_development_audit (
 id uuid PRIMARY KEY, record_id uuid NOT NULL, action varchar(30) NOT NULL,
 actor_id uuid NOT NULL REFERENCES app_user(id), created_at timestamp NOT NULL,
 before json NOT NULL DEFAULT '{}', after json NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS ix_referral_audit_record_time ON referral_development_audit(record_id,created_at,id);
COMMIT;

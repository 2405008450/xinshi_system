-- 排班重构：员工周模板、单日覆盖与译员明确可用状态。
-- 执行前请按发布手册备份数据库。本脚本可重复执行。
BEGIN;

CREATE TABLE IF NOT EXISTS employee_shift_template (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    weekday SMALLINT NOT NULL,
    effective_from DATE NOT NULL,
    shift_code VARCHAR(30) NOT NULL,
    start_time TIME,
    end_time TIME,
    updated_by UUID,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_employee_shift_template_user
        FOREIGN KEY (user_id) REFERENCES app_user(id) ON DELETE CASCADE,
    CONSTRAINT uq_employee_shift_template_version
        UNIQUE (user_id, weekday, effective_from),
    CONSTRAINT ck_employee_shift_template_weekday
        CHECK (weekday >= 1 AND weekday <= 7),
    CONSTRAINT ck_employee_shift_template_code
        CHECK (shift_code IN ('early_early', 'early', 'late', 'late_late', 'weekend_duty', 'custom', 'off', 'unassigned')),
    CONSTRAINT ck_employee_shift_template_custom_time
        CHECK (shift_code <> 'custom' OR (start_time IS NOT NULL AND end_time IS NOT NULL AND end_time > start_time)),
    CONSTRAINT ck_employee_shift_template_weekend
        CHECK (shift_code <> 'weekend_duty' OR weekday IN (6, 7))
);

CREATE INDEX IF NOT EXISTS ix_employee_shift_template_lookup
    ON employee_shift_template(user_id, weekday, effective_from DESC);

CREATE TABLE IF NOT EXISTS employee_shift_override (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    schedule_date DATE NOT NULL,
    shift_code VARCHAR(30) NOT NULL,
    start_time TIME,
    end_time TIME,
    note TEXT,
    updated_by UUID,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_employee_shift_override_user
        FOREIGN KEY (user_id) REFERENCES app_user(id) ON DELETE CASCADE,
    CONSTRAINT uq_employee_shift_override_date UNIQUE (user_id, schedule_date),
    CONSTRAINT ck_employee_shift_override_code
        CHECK (shift_code IN ('early_early', 'early', 'late', 'late_late', 'weekend_duty', 'custom', 'off', 'unassigned')),
    CONSTRAINT ck_employee_shift_override_custom_time
        CHECK (shift_code <> 'custom' OR (start_time IS NOT NULL AND end_time IS NOT NULL AND end_time > start_time)),
    CONSTRAINT ck_employee_shift_override_weekend
        CHECK (shift_code <> 'weekend_duty' OR EXTRACT(ISODOW FROM schedule_date) IN (6, 7))
);

CREATE INDEX IF NOT EXISTS ix_employee_shift_override_lookup
    ON employee_shift_override(schedule_date, user_id);

ALTER TABLE translator_schedule
    ADD COLUMN IF NOT EXISTS availability_status VARCHAR(30);

UPDATE translator_schedule
SET availability_status = CASE
    WHEN available_time_slot = '本周期不可接稿' THEN 'cycle_blocked'
    ELSE 'available'
END
WHERE availability_status IS NULL;

ALTER TABLE translator_schedule
    ALTER COLUMN availability_status SET DEFAULT 'available';
ALTER TABLE translator_schedule
    ALTER COLUMN availability_status SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_translator_schedule_availability_status'
    ) THEN
        ALTER TABLE translator_schedule
            ADD CONSTRAINT ck_translator_schedule_availability_status
            CHECK (availability_status IN ('available', 'unavailable', 'cycle_blocked'));
    END IF;
END
$$;

COMMIT;

-- 回滚说明：确认新表无业务数据后可 DROP 两张 employee_shift_* 表；
-- translator_schedule.availability_status 在新代码运行后属于业务字段，不建议直接删除。

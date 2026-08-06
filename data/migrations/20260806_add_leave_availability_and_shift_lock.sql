BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'employee_leave'
          AND column_name = 'start_date'
          AND data_type = 'date'
    ) THEN
        ALTER TABLE employee_leave
            ALTER COLUMN start_date TYPE TIMESTAMP WITHOUT TIME ZONE
            USING start_date::timestamp;
        ALTER TABLE employee_leave
            ALTER COLUMN end_date TYPE TIMESTAMP WITHOUT TIME ZONE
            USING (end_date + INTERVAL '1 day')::timestamp;
    END IF;
END $$;

ALTER TABLE employee_leave
    ADD COLUMN IF NOT EXISTS created_by UUID,
    ADD COLUMN IF NOT EXISTS updated_by UUID,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

UPDATE employee_leave
SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
WHERE updated_at IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_employee_leave_employee') THEN
        ALTER TABLE employee_leave
            ADD CONSTRAINT fk_employee_leave_employee
            FOREIGN KEY (employee_id) REFERENCES app_user(id) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_employee_leave_created_by') THEN
        ALTER TABLE employee_leave
            ADD CONSTRAINT fk_employee_leave_created_by
            FOREIGN KEY (created_by) REFERENCES app_user(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_employee_leave_updated_by') THEN
        ALTER TABLE employee_leave
            ADD CONSTRAINT fk_employee_leave_updated_by
            FOREIGN KEY (updated_by) REFERENCES app_user(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_employee_leave_employee_time
    ON employee_leave (employee_id, start_date, end_date);

CREATE TABLE IF NOT EXISTS employee_shift_lock (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    effective_from DATE NOT NULL,
    is_locked BOOLEAN NOT NULL DEFAULT FALSE,
    reason VARCHAR(500),
    changed_by UUID,
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_employee_shift_lock_user
        FOREIGN KEY (user_id) REFERENCES app_user(id) ON DELETE CASCADE,
    CONSTRAINT fk_employee_shift_lock_changed_by
        FOREIGN KEY (changed_by) REFERENCES app_user(id) ON DELETE SET NULL,
    CONSTRAINT uq_employee_shift_lock_version UNIQUE (user_id, effective_from),
    CONSTRAINT ck_employee_shift_lock_monday
        CHECK (EXTRACT(ISODOW FROM effective_from) = 1)
);

CREATE INDEX IF NOT EXISTS ix_employee_shift_lock_user_effective
    ON employee_shift_lock (user_id, effective_from DESC);

CREATE TABLE IF NOT EXISTS employee_shift_override_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    schedule_date DATE NOT NULL,
    action VARCHAR(20) NOT NULL,
    shift_code VARCHAR(30),
    start_time TIME,
    end_time TIME,
    reason TEXT,
    was_locked BOOLEAN NOT NULL DEFAULT FALSE,
    changed_by UUID,
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_shift_override_audit_user
        FOREIGN KEY (user_id) REFERENCES app_user(id) ON DELETE CASCADE,
    CONSTRAINT fk_shift_override_audit_changed_by
        FOREIGN KEY (changed_by) REFERENCES app_user(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_shift_override_audit_user_date
    ON employee_shift_override_audit (user_id, schedule_date, changed_at);

COMMIT;

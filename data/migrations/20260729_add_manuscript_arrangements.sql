BEGIN;

CREATE TABLE IF NOT EXISTS manuscript_dispatch (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(20) NOT NULL,
    translation_project_id UUID NOT NULL,
    sub_order_id UUID,
    order_no_snapshot VARCHAR(80) NOT NULL,
    project_name_snapshot VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    remarks TEXT,
    created_by UUID,
    created_by_name VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP,
    cancelled_at TIMESTAMP,
    previous_order_status VARCHAR(50),
    CONSTRAINT fk_manuscript_dispatch_project
        FOREIGN KEY (translation_project_id)
        REFERENCES translation_project(id) ON DELETE CASCADE,
    CONSTRAINT fk_manuscript_dispatch_sub_order
        FOREIGN KEY (sub_order_id)
        REFERENCES translation_sub_order(id) ON DELETE CASCADE,
    CONSTRAINT fk_manuscript_dispatch_creator
        FOREIGN KEY (created_by)
        REFERENCES app_user(id) ON DELETE SET NULL,
    CONSTRAINT ck_manuscript_dispatch_entity
        CHECK (
            (entity_type = 'project' AND sub_order_id IS NULL)
            OR
            (entity_type = 'suborder' AND sub_order_id IS NOT NULL)
        ),
    CONSTRAINT ck_manuscript_dispatch_status
        CHECK (status IN ('draft', 'ready', 'partially_sent', 'sent', 'cancelled'))
);

CREATE TABLE IF NOT EXISTS manuscript_arrangement (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dispatch_id UUID NOT NULL,
    entity_type VARCHAR(20) NOT NULL,
    translation_project_id UUID NOT NULL,
    sub_order_id UUID,
    translator_id UUID NOT NULL,
    order_no_snapshot VARCHAR(80) NOT NULL,
    project_name_snapshot VARCHAR(255) NOT NULL,
    translator_name_snapshot VARCHAR(255) NOT NULL,
    cooperation_type_snapshot VARCHAR(50),
    recipient_email VARCHAR(255),
    planned_word_count BIGINT,
    actual_word_count BIGINT,
    translation_scope TEXT,
    settlement_method VARCHAR(30),
    custom_settlement_method VARCHAR(100),
    translator_unit_price NUMERIC(14, 4),
    translator_total_price NUMERIC(14, 2),
    planned_delivery_at TIMESTAMP,
    manuscript_source_path TEXT,
    email_subject VARCHAR(500),
    email_body TEXT,
    remarks TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_by UUID,
    created_by_name VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    send_attempted_at TIMESTAMP,
    sent_at TIMESTAMP,
    delivery_recipient VARCHAR(255),
    delivery_mode VARCHAR(20),
    smtp_message_id VARCHAR(255),
    send_error TEXT,
    CONSTRAINT fk_manuscript_arrangement_dispatch
        FOREIGN KEY (dispatch_id)
        REFERENCES manuscript_dispatch(id) ON DELETE CASCADE,
    CONSTRAINT fk_manuscript_arrangement_project
        FOREIGN KEY (translation_project_id)
        REFERENCES translation_project(id) ON DELETE CASCADE,
    CONSTRAINT fk_manuscript_arrangement_sub_order
        FOREIGN KEY (sub_order_id)
        REFERENCES translation_sub_order(id) ON DELETE CASCADE,
    CONSTRAINT fk_manuscript_arrangement_translator
        FOREIGN KEY (translator_id)
        REFERENCES translator(id) ON DELETE RESTRICT,
    CONSTRAINT fk_manuscript_arrangement_creator
        FOREIGN KEY (created_by)
        REFERENCES app_user(id) ON DELETE SET NULL,
    CONSTRAINT uq_manuscript_arrangement_dispatch_translator
        UNIQUE (dispatch_id, translator_id),
    CONSTRAINT ck_manuscript_arrangement_entity_type
        CHECK (entity_type IN ('project', 'suborder')),
    CONSTRAINT ck_manuscript_arrangement_status
        CHECK (status IN ('draft', 'ready', 'sent', 'failed', 'cancelled')),
    CONSTRAINT ck_manuscript_arrangement_planned_words
        CHECK (planned_word_count IS NULL OR planned_word_count >= 0),
    CONSTRAINT ck_manuscript_arrangement_actual_words
        CHECK (actual_word_count IS NULL OR actual_word_count >= 0)
);

ALTER TABLE manuscript_arrangement
    ADD COLUMN IF NOT EXISTS dispatch_id UUID,
    ADD COLUMN IF NOT EXISTS planned_word_count BIGINT,
    ADD COLUMN IF NOT EXISTS actual_word_count BIGINT,
    ADD COLUMN IF NOT EXISTS translation_scope TEXT,
    ADD COLUMN IF NOT EXISTS settlement_method VARCHAR(30),
    ADD COLUMN IF NOT EXISTS custom_settlement_method VARCHAR(100),
    ADD COLUMN IF NOT EXISTS translator_unit_price NUMERIC(14, 4),
    ADD COLUMN IF NOT EXISTS translator_total_price NUMERIC(14, 2),
    ADD COLUMN IF NOT EXISTS send_attempted_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS delivery_recipient VARCHAR(255),
    ADD COLUMN IF NOT EXISTS delivery_mode VARCHAR(20),
    ADD COLUMN IF NOT EXISTS smtp_message_id VARCHAR(255),
    ADD COLUMN IF NOT EXISTS send_error TEXT;

ALTER TABLE manuscript_dispatch
    ADD COLUMN IF NOT EXISTS previous_order_status VARCHAR(50);

INSERT INTO manuscript_dispatch (
    id,
    entity_type,
    translation_project_id,
    sub_order_id,
    order_no_snapshot,
    project_name_snapshot,
    status,
    created_by,
    created_by_name,
    created_at,
    updated_at,
    confirmed_at,
    cancelled_at
)
SELECT
    ma.id,
    ma.entity_type,
    ma.translation_project_id,
    ma.sub_order_id,
    ma.order_no_snapshot,
    ma.project_name_snapshot,
    CASE
        WHEN ma.status = 'sent' THEN 'sent'
        WHEN ma.status = 'cancelled' THEN 'cancelled'
        WHEN ma.status = 'draft' THEN 'draft'
        ELSE 'ready'
    END,
    ma.created_by,
    ma.created_by_name,
    ma.created_at,
    ma.updated_at,
    CASE
        WHEN ma.status = 'draft' THEN NULL
        ELSE COALESCE(ma.updated_at, ma.created_at)
    END,
    CASE
        WHEN ma.status = 'cancelled' THEN COALESCE(ma.updated_at, ma.created_at)
        ELSE NULL
    END
FROM manuscript_arrangement ma
WHERE ma.dispatch_id IS NULL
ON CONFLICT (id) DO NOTHING;

UPDATE manuscript_arrangement
SET dispatch_id = id
WHERE dispatch_id IS NULL;

CREATE TABLE IF NOT EXISTS manuscript_delivery_milestone (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    arrangement_id UUID NOT NULL,
    milestone_type VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL,
    sequence_no INTEGER NOT NULL,
    planned_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_manuscript_milestone_arrangement
        FOREIGN KEY (arrangement_id)
        REFERENCES manuscript_arrangement(id) ON DELETE CASCADE,
    CONSTRAINT uq_manuscript_milestone_sequence
        UNIQUE (arrangement_id, sequence_no),
    CONSTRAINT ck_manuscript_milestone_type
        CHECK (milestone_type IN ('phase', 'final')),
    CONSTRAINT ck_manuscript_milestone_sequence
        CHECK (sequence_no >= 1)
);

INSERT INTO manuscript_delivery_milestone (
    arrangement_id,
    milestone_type,
    name,
    sequence_no,
    planned_at
)
SELECT ma.id, 'final', '全稿', 1, ma.planned_delivery_at
FROM manuscript_arrangement ma
WHERE ma.planned_delivery_at IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM manuscript_delivery_milestone mdm
      WHERE mdm.arrangement_id = ma.id
        AND mdm.milestone_type = 'final'
  );

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_manuscript_arrangement_dispatch'
    ) THEN
        ALTER TABLE manuscript_arrangement
            ADD CONSTRAINT fk_manuscript_arrangement_dispatch
            FOREIGN KEY (dispatch_id)
            REFERENCES manuscript_dispatch(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_manuscript_arrangement_dispatch_translator'
    ) THEN
        ALTER TABLE manuscript_arrangement
            ADD CONSTRAINT uq_manuscript_arrangement_dispatch_translator
            UNIQUE (dispatch_id, translator_id);
    END IF;
END $$;

ALTER TABLE manuscript_arrangement
    ALTER COLUMN dispatch_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS ix_manuscript_dispatch_project_status
    ON manuscript_dispatch(translation_project_id, status);

CREATE INDEX IF NOT EXISTS ix_manuscript_dispatch_order_created
    ON manuscript_dispatch(order_no_snapshot, created_at);

CREATE INDEX IF NOT EXISTS ix_manuscript_arrangement_project_status
    ON manuscript_arrangement(translation_project_id, status);

CREATE INDEX IF NOT EXISTS ix_manuscript_arrangement_translator_status
    ON manuscript_arrangement(translator_id, status);

CREATE INDEX IF NOT EXISTS ix_manuscript_milestone_planned_at
    ON manuscript_delivery_milestone(planned_at);

COMMIT;

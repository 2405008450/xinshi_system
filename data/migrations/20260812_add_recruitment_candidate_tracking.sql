BEGIN;

CREATE TABLE IF NOT EXISTS recruitment_resume_source (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    label VARCHAR(100) NOT NULL,
    is_custom BOOLEAN NOT NULL DEFAULT FALSE,
    created_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_recruitment_resume_source_label UNIQUE (label)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_recruitment_resume_source_label_normalized
    ON recruitment_resume_source (lower(trim(label)));

INSERT INTO recruitment_resume_source (label, is_custom)
VALUES
    ('BOSS', FALSE),
    ('智联', FALSE),
    ('小红书', FALSE),
    ('微信', FALSE),
    ('广外校友推荐', FALSE)
ON CONFLICT (label) DO NOTHING;

ALTER TABLE recruitment_candidate
    ADD COLUMN IF NOT EXISTS resume_source_id UUID REFERENCES recruitment_resume_source(id) ON DELETE SET NULL;
ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS first_interview_date DATE;
ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS first_interview_details TEXT;
ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS second_interview_date DATE;
ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS second_interview_details TEXT;

UPDATE recruitment_candidate
SET first_interview_date = interview_at::date
WHERE first_interview_date IS NULL AND interview_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS recruitment_candidate_communication (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id UUID NOT NULL REFERENCES recruitment_candidate(id) ON DELETE CASCADE,
    sequence_no INTEGER NOT NULL,
    communication_date DATE NOT NULL,
    details TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_recruitment_candidate_communication_sequence UNIQUE (candidate_id, sequence_no),
    CONSTRAINT ck_recruitment_candidate_communication_sequence CHECK (sequence_no > 0)
);
ALTER TABLE recruitment_candidate_communication ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE recruitment_candidate_communication ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;
CREATE INDEX IF NOT EXISTS ix_recruitment_candidate_communication_candidate
    ON recruitment_candidate_communication(candidate_id);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='recruitment_candidate' AND column_name='entry_date') THEN
        EXECUTE 'UPDATE recruitment_candidate SET actual_onboard_date = COALESCE(actual_onboard_date, entry_date)';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='recruitment_candidate' AND column_name='resume_source') THEN
        EXECUTE $sql$
            INSERT INTO recruitment_resume_source (label, is_custom)
            SELECT DISTINCT trim(candidate.resume_source), TRUE
            FROM recruitment_candidate candidate
            WHERE candidate.resume_source IS NOT NULL AND trim(candidate.resume_source) <> ''
            ON CONFLICT DO NOTHING
        $sql$;
        EXECUTE $sql$
            UPDATE recruitment_candidate candidate
            SET resume_source_id = source.id
            FROM recruitment_resume_source source
            WHERE candidate.resume_source_id IS NULL
              AND lower(trim(candidate.resume_source)) = lower(trim(source.label))
        $sql$;
    END IF;
END
$$;

COMMIT;

BEGIN;

CREATE TABLE IF NOT EXISTS recruitment_candidate_interview (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id UUID NOT NULL REFERENCES recruitment_candidate(id) ON DELETE CASCADE,
    round_no INTEGER NOT NULL,
    interview_date DATE,
    details TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_recruitment_candidate_interview_round UNIQUE (candidate_id, round_no),
    CONSTRAINT ck_recruitment_candidate_interview_round CHECK (round_no > 0)
);

CREATE INDEX IF NOT EXISTS ix_recruitment_candidate_interview_candidate
    ON recruitment_candidate_interview(candidate_id);

-- 把旧的一面、二面字段迁入可变轮次表；二面存在但一面为空时补一个空的一面占位。
INSERT INTO recruitment_candidate_interview
    (candidate_id, round_no, interview_date, details)
SELECT id, 1, first_interview_date, first_interview_details
FROM recruitment_candidate
WHERE first_interview_date IS NOT NULL OR first_interview_details IS NOT NULL
ON CONFLICT (candidate_id, round_no) DO NOTHING;

INSERT INTO recruitment_candidate_interview
    (candidate_id, round_no, interview_date, details)
SELECT id, 1, NULL, NULL
FROM recruitment_candidate
WHERE second_interview_date IS NOT NULL OR second_interview_details IS NOT NULL
ON CONFLICT (candidate_id, round_no) DO NOTHING;

INSERT INTO recruitment_candidate_interview
    (candidate_id, round_no, interview_date, details)
SELECT id, 2, second_interview_date, second_interview_details
FROM recruitment_candidate
WHERE second_interview_date IS NOT NULL OR second_interview_details IS NOT NULL
ON CONFLICT (candidate_id, round_no) DO NOTHING;

COMMIT;

ALTER TABLE manuscript_arrangement
    ADD COLUMN IF NOT EXISTS completion_remarks VARCHAR(255);

COMMENT ON COLUMN manuscript_arrangement.completion_remarks
    IS '译员回稿后，本次派稿任务的完成情况备注';

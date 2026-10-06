BEGIN;
ALTER TABLE annotation_project ADD COLUMN IF NOT EXISTS parent_project_id uuid;
ALTER TABLE annotation_project ADD COLUMN IF NOT EXISTS child_sequence_no integer;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_annotation_project_parent') THEN
        ALTER TABLE annotation_project ADD CONSTRAINT fk_annotation_project_parent FOREIGN KEY (parent_project_id) REFERENCES annotation_project(id) ON DELETE RESTRICT;
        ALTER TABLE annotation_project ADD CONSTRAINT uq_annotation_project_child_sequence UNIQUE (parent_project_id, child_sequence_no);
        ALTER TABLE annotation_project ADD CONSTRAINT ck_annotation_project_child_sequence CHECK ((parent_project_id IS NULL AND child_sequence_no IS NULL) OR (parent_project_id IS NOT NULL AND child_sequence_no IS NOT NULL AND child_sequence_no > 0));
        ALTER TABLE annotation_project ADD CONSTRAINT ck_annotation_project_not_self CHECK (parent_project_id IS NULL OR parent_project_id <> id);
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS ix_annotation_project_parent ON annotation_project(parent_project_id);
COMMIT;

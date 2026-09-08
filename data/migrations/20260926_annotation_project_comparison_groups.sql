-- 标注项目比较组及其项目成员关系。

CREATE TABLE IF NOT EXISTS annotation_project_comparison_group (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(150) NOT NULL,
    description TEXT NOT NULL,
    created_by UUID NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_annotation_comparison_group_creator
        FOREIGN KEY (created_by) REFERENCES app_user(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_annotation_comparison_group_created_at
    ON annotation_project_comparison_group (created_at);

CREATE TABLE IF NOT EXISTS annotation_project_comparison_member (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL,
    project_id UUID NOT NULL,
    sequence_no INTEGER NOT NULL,
    CONSTRAINT fk_annotation_comparison_member_group
        FOREIGN KEY (group_id) REFERENCES annotation_project_comparison_group(id) ON DELETE CASCADE,
    CONSTRAINT fk_annotation_comparison_member_project
        FOREIGN KEY (project_id) REFERENCES annotation_project(id) ON DELETE CASCADE,
    CONSTRAINT uq_annotation_comparison_member_project UNIQUE (group_id, project_id),
    CONSTRAINT uq_annotation_comparison_member_sequence UNIQUE (group_id, sequence_no),
    CONSTRAINT ck_annotation_comparison_member_sequence CHECK (sequence_no >= 1 AND sequence_no <= 10)
);

CREATE INDEX IF NOT EXISTS ix_annotation_comparison_member_project
    ON annotation_project_comparison_member (project_id);

BEGIN;

ALTER TABLE annotation_account_assignment
    ADD COLUMN IF NOT EXISTS custom_values JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE annotation_custom_field_definition
    DROP CONSTRAINT IF EXISTS ck_annotation_custom_field_table;
ALTER TABLE annotation_custom_field_definition
    ADD CONSTRAINT ck_annotation_custom_field_table
    CHECK (table_code IN ('project','account','trial','assignment','account_assignment'));

ALTER TABLE annotation_custom_field_definition
    DROP CONSTRAINT IF EXISTS ck_annotation_custom_field_scope;
ALTER TABLE annotation_custom_field_definition
    ADD CONSTRAINT ck_annotation_custom_field_scope CHECK (
        (table_code IN ('project','account') AND project_id IS NULL)
        OR
        (table_code IN ('trial','assignment','account_assignment') AND project_id IS NOT NULL)
    );

COMMENT ON COLUMN annotation_account_assignment.custom_values
    IS '当前项目账号表动态字段值，释放后随分配履历保留';

COMMIT;

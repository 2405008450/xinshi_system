BEGIN;
CREATE TABLE IF NOT EXISTS annotation_material_folder (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES annotation_project(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES annotation_material_folder(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    CONSTRAINT uq_annotation_material_folder_sibling UNIQUE(project_id, parent_id, name)
);
CREATE INDEX IF NOT EXISTS ix_annotation_material_folder_project_id ON annotation_material_folder(project_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_annotation_material_folder_root ON annotation_material_folder(project_id, name) WHERE parent_id IS NULL;
ALTER TABLE annotation_material_file ADD COLUMN IF NOT EXISTS folder_id UUID;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'annotation_material_file'::regclass AND conname = 'fk_annotation_material_file_folder') THEN
        ALTER TABLE annotation_material_file ADD CONSTRAINT fk_annotation_material_file_folder FOREIGN KEY(folder_id) REFERENCES annotation_material_folder(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'annotation_material_file'::regclass AND conname = 'ck_annotation_material_folder_category') THEN
        ALTER TABLE annotation_material_file ADD CONSTRAINT ck_annotation_material_folder_category CHECK(folder_id IS NULL OR category = 'project');
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS ix_annotation_material_file_folder_id ON annotation_material_file(folder_id);
COMMIT;

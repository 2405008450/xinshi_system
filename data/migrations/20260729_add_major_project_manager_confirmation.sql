ALTER TABLE translation_project
ADD COLUMN IF NOT EXISTS major_project_manager_confirmation VARCHAR(255);

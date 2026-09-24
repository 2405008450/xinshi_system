BEGIN;
ALTER TABLE resource_development_record ADD COLUMN IF NOT EXISTS historical_only boolean NOT NULL DEFAULT false;
ALTER TABLE resource_development_record ADD COLUMN IF NOT EXISTS historical_markers json NOT NULL DEFAULT '{}';
COMMIT;
